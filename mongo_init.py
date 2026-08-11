"""
Auto-creates the MongoDB database and all collections with indexes.
Called once from config/apps.py when Django starts.
"""

import logging

logger = logging.getLogger(__name__)


def initialize_mongodb():
    try:
        import mongo_store
        database = mongo_store.db()

        existing = database.list_collection_names()

        _setup_events(database, existing)
        _setup_event_photos(database, existing)
        _setup_guest_uploads(database, existing)
        _setup_photo_matches(database, existing)

        logger.info('MongoDB ready — database: "%s"', database.name)

    except Exception as exc:
        # MongoDB being unavailable must not crash Django startup
        logger.warning('MongoDB init skipped: %s', exc)


def _setup_events(db, existing):
    if 'events' not in existing:
        db.create_collection('events')
        logger.info('Created collection: events')

    col = db['events']
    col.create_index('event_id', unique=True, name='idx_event_id')
    col.create_index('slug', name='idx_slug')


def _setup_event_photos(db, existing):
    if 'event_photos' not in existing:
        db.create_collection('event_photos')
        logger.info('Created collection: event_photos')

    col = db['event_photos']
    col.create_index('photo_id', unique=True, name='idx_photo_id')
    col.create_index('event_id', name='idx_event_id')
    col.create_index(
        [('event_id', 1), ('processed', 1)],
        name='idx_event_processed',
    )


def _setup_guest_uploads(db, existing):
    if 'guest_uploads' not in existing:
        db.create_collection('guest_uploads')
        logger.info('Created collection: guest_uploads')

    col = db['guest_uploads']
    col.create_index('upload_id', unique=True, name='idx_upload_id')
    col.create_index('event_id', name='idx_event_id')
    col.create_index('status', name='idx_status')


def _setup_photo_matches(db, existing):
    if 'photo_matches' not in existing:
        db.create_collection('photo_matches')
        logger.info('Created collection: photo_matches')

    col = db['photo_matches']
    col.create_index(
        [('upload_id', 1), ('photo_id', 1)],
        unique=True,
        name='idx_upload_photo',
    )
    col.create_index('upload_id', name='idx_upload_id')
    col.create_index('confidence', name='idx_confidence')
