import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class PhotosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'photos'

    def ready(self):
        # Start auto-indexing background thread (only in main process)
        import os
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('test'):
            _start_auto_indexer()


def _start_auto_indexer():
    import os
    # Avoid double-start in Django dev server (which forks)
    if os.environ.get('_INDEXER_STARTED'):
        return
    os.environ['_INDEXER_STARTED'] = '1'

    t = threading.Thread(target=_indexer_loop, daemon=True, name='ArcFaceAutoIndexer')
    t.start()
    logger.info('ArcFace auto-indexer started (30s interval)')


def _indexer_loop():
    import time
    # Wait for Django to fully boot before first run
    time.sleep(10)

    while True:
        try:
            _index_pending_photos()
        except Exception:
            logger.exception('Auto-indexer error')
        time.sleep(30)


def _index_pending_photos():
    from photos.models import EventPhoto
    from photos.tasks import process_event_photo

    pending = EventPhoto.objects.filter(processed=False).order_by('uploaded_at')
    count = pending.count()
    if count == 0:
        return

    logger.info('Auto-indexer: %d unprocessed photo(s) found', count)
    for photo in pending:
        try:
            process_event_photo(photo.pk)
            logger.info('Auto-indexed photo %s', photo.pk)
        except Exception:
            logger.exception('Failed to index photo %s', photo.pk)
