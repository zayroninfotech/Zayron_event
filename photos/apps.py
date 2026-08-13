import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PhotosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'photos'

    def ready(self):
        import os
        # Init MongoDB collections/indexes on startup
        try:
            import mongo_store
            mongo_store.init_collections()
            logger.info('MongoDB collections initialized')
        except Exception:
            logger.exception('Failed to initialize MongoDB collections')

        # Start auto-indexer background thread (main process only)
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('test'):
            _start_auto_indexer()


def _start_auto_indexer():
    import os
    if os.environ.get('_INDEXER_STARTED'):
        return
    os.environ['_INDEXER_STARTED'] = '1'
    t = threading.Thread(target=_indexer_loop, daemon=True, name='ArcFaceAutoIndexer')
    t.start()
    logger.info('ArcFace auto-indexer started (30s interval)')


def _indexer_loop():
    import time
    time.sleep(60)
    while True:
        try:
            _index_pending_photos()
        except Exception:
            logger.exception('Auto-indexer error')
        time.sleep(30)


def _index_pending_photos():
    import mongo_store
    from photos.models import EventPhoto
    from photos.tasks import process_event_photo

    pending_docs = mongo_store.get_photos_unprocessed()
    if not pending_docs:
        return

    logger.info('Auto-indexer: %d unprocessed photo(s)', len(pending_docs))
    for doc in pending_docs:
        photo = EventPhoto(doc)
        try:
            process_event_photo(photo.pk)
            logger.info('Auto-indexed photo %s', photo.pk)
        except Exception:
            logger.exception('Failed to index photo %s', photo.pk)
