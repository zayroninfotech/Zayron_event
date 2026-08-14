"""
MongoDB access layer — ALL application data lives here.
Django's SQLite (auth.db) is used ONLY for auth/sessions/tokens (Django internals).

Collections:
  counters        - auto-increment ID sequences
  events          - Event records
  event_photos    - Photo metadata + ArcFace embeddings
  guest_uploads   - Guest selfie uploads
  photo_matches   - Guest → photo match results
"""

from functools import lru_cache
from datetime import datetime
from pymongo import MongoClient, DESCENDING, ASCENDING
from pymongo.database import Database


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    from django.conf import settings
    uri = getattr(settings, 'MONGO_URI', '')
    if uri:
        return MongoClient(uri)
    host = settings.MONGO_HOST
    port = settings.MONGO_PORT
    user = getattr(settings, 'MONGO_USER', '')
    password = getattr(settings, 'MONGO_PASSWORD', '')
    auth_source = getattr(settings, 'MONGO_AUTH_SOURCE', 'admin')
    if user and password:
        return MongoClient(host=host, port=port, username=user, password=password, authSource=auth_source)
    return MongoClient(host=host, port=port)


def db() -> Database:
    from django.conf import settings
    return _client()[settings.MONGO_DB]


def events_col():   return db()['events']
def photos_col():   return db()['event_photos']
def guests_col():   return db()['guest_uploads']
def matches_col():  return db()['photo_matches']
def counters_col(): return db()['counters']


# ── Auto-increment IDs ────────────────────────────────────────────────────

def _next_id(name: str) -> int:
    result = counters_col().find_one_and_update(
        {'_id': name},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True,
    )
    return result['seq']


# ── Collection init ───────────────────────────────────────────────────────

def _safe_index(col, keys, **kwargs):
    try:
        col.create_index(keys, **kwargs)
    except Exception:
        pass


def init_collections():
    """Create indexes for all collections (idempotent, skips conflicts)."""
    ec = events_col()
    _safe_index(ec, 'id', unique=True, name='idx_id')
    _safe_index(ec, 'slug', unique=True, name='idx_slug')
    _safe_index(ec, 'created_by_id', name='idx_created_by')

    pc = photos_col()
    _safe_index(pc, 'id', unique=True, name='idx_id')
    _safe_index(pc, 'event_id', name='idx_event_id2')
    _safe_index(pc, [('uploaded_at', DESCENDING)], name='idx_uploaded_at')

    gc = guests_col()
    _safe_index(gc, 'id', unique=True, name='idx_id')
    _safe_index(gc, 'event_id', name='idx_event_id2')
    _safe_index(gc, [('created_at', DESCENDING)], name='idx_created_at')

    mc = matches_col()
    _safe_index(mc, 'id', unique=True, name='idx_id')
    _safe_index(mc, 'guest_upload_id', name='idx_guest_id')
    _safe_index(mc, 'photo_id', name='idx_photo_id')
    _safe_index(
        mc,
        [('guest_upload_id', ASCENDING), ('photo_id', ASCENDING)],
        unique=True,
        name='idx_guest_photo',
    )


# ── Event CRUD ────────────────────────────────────────────────────────────

def create_event(data: dict) -> dict:
    data['id'] = _next_id('events')
    data.setdefault('created_at', datetime.utcnow())
    data.setdefault('agent_sync_enabled', False)
    data.setdefault('watch_folder', '')
    data.setdefault('description', '')
    data.setdefault('qr_code', '')
    events_col().insert_one(data)
    data.pop('_id', None)
    return data


def get_event_by_id(event_id: int) -> dict | None:
    return events_col().find_one({'id': event_id}, {'_id': 0})


def get_event_by_slug(slug: str) -> dict | None:
    return events_col().find_one({'slug': slug}, {'_id': 0})


def get_events_by_user(user_id) -> list[dict]:
    return list(events_col().find({'created_by_id': user_id}, {'_id': 0}).sort('created_at', DESCENDING))


def update_event(event_id: int, data: dict):
    events_col().update_one({'id': event_id}, {'$set': data})


def delete_event(event_id: int):
    photo_ids = [p['id'] for p in photos_col().find({'event_id': event_id}, {'id': 1}) if p.get('id') is not None]
    guest_ids = [g['id'] for g in guests_col().find({'event_id': event_id}, {'id': 1}) if g.get('id') is not None]
    events_col().delete_one({'id': event_id})
    photos_col().delete_many({'event_id': event_id})
    guests_col().delete_many({'event_id': event_id})
    if photo_ids:
        matches_col().delete_many({'photo_id': {'$in': photo_ids}})
    if guest_ids:
        matches_col().delete_many({'guest_upload_id': {'$in': guest_ids}})


# ── EventPhoto CRUD ───────────────────────────────────────────────────────

def create_photo(data: dict) -> dict:
    data['id'] = _next_id('event_photos')
    data.setdefault('uploaded_at', datetime.utcnow())
    data.setdefault('processed', False)
    data.setdefault('face_count', 0)
    data.setdefault('face_encodings', [])
    data.setdefault('thumbnail', '')
    photos_col().insert_one(data)
    data.pop('_id', None)
    return data


def get_photo_by_id(photo_id: int) -> dict | None:
    return photos_col().find_one({'id': photo_id}, {'_id': 0})


def get_photos_by_event(event_id: int) -> list[dict]:
    return list(photos_col().find({'event_id': event_id}, {'_id': 0}).sort('uploaded_at', DESCENDING))


def get_photos_unprocessed(event_id: int = None) -> list[dict]:
    q = {'processed': False}
    if event_id:
        q['event_id'] = event_id
    return list(photos_col().find(q, {'_id': 0}).sort('uploaded_at', ASCENDING))


def update_photo(photo_id: int, data: dict):
    photos_col().update_one({'id': photo_id}, {'$set': data})


def delete_photo(photo_id: int):
    photos_col().delete_one({'id': photo_id})
    matches_col().delete_many({'photo_id': photo_id})


def count_photos(event_id: int) -> int:
    return photos_col().count_documents({'event_id': event_id})


def count_processed_photos(event_id: int) -> int:
    return photos_col().count_documents({'event_id': event_id, 'processed': True})


def get_last_photo(event_id: int) -> dict | None:
    return photos_col().find_one({'event_id': event_id}, {'_id': 0}, sort=[('uploaded_at', DESCENDING)])


def get_photos_values(event_id: int) -> list[dict]:
    return list(photos_col().find(
        {'event_id': event_id},
        {'id': 1, 'processed': 1, 'face_count': 1, 'uploaded_at': 1, '_id': 0},
    ))


def get_event_photo_encodings(event_id: int) -> list[dict]:
    """Return {id, face_encodings} for all processed photos in an event."""
    return list(photos_col().find(
        {'event_id': event_id, 'processed': True, 'face_encodings': {'$not': {'$size': 0}}},
        {'id': 1, 'face_encodings': 1, '_id': 0},
    ))


def get_photos_for_events(event_ids: list[int]) -> list[dict]:
    return list(photos_col().find(
        {'event_id': {'$in': event_ids}},
        {'_id': 0},
    ).sort('uploaded_at', DESCENDING).limit(100))


# ── GuestUpload CRUD ──────────────────────────────────────────────────────

def create_guest(data: dict) -> dict:
    data['id'] = _next_id('guest_uploads')
    data.setdefault('created_at', datetime.utcnow())
    data.setdefault('face_encoding', [])
    data.setdefault('status', 'pending')
    data.setdefault('task_id', '')
    guests_col().insert_one(data)
    data.pop('_id', None)
    return data


def get_guest_by_id(upload_id: int) -> dict | None:
    return guests_col().find_one({'id': upload_id}, {'_id': 0})


def get_guests_by_event(event_id: int) -> list[dict]:
    return list(guests_col().find({'event_id': event_id}, {'_id': 0}))


def update_guest(upload_id: int, data: dict):
    guests_col().update_one({'id': upload_id}, {'$set': data})


def count_guests(event_id: int) -> int:
    return guests_col().count_documents({'event_id': event_id})


def count_guests_for_events(event_ids: list[int]) -> int:
    return guests_col().count_documents({'event_id': {'$in': event_ids}})


def delete_guest_biometric(upload_id: int):
    guests_col().update_one(
        {'id': upload_id},
        {'$set': {'face_encoding': [], 'selfie_deleted': True}},
    )


# ── PhotoMatch CRUD ───────────────────────────────────────────────────────

def create_or_update_match(guest_upload_id: int, photo_id: int, confidence: float) -> dict:
    existing = matches_col().find_one(
        {'guest_upload_id': guest_upload_id, 'photo_id': photo_id},
        {'_id': 0},
    )
    if existing:
        matches_col().update_one(
            {'guest_upload_id': guest_upload_id, 'photo_id': photo_id},
            {'$set': {'confidence': confidence}},
        )
        existing['confidence'] = confidence
        return existing
    data = {
        'id': _next_id('photo_matches'),
        'guest_upload_id': guest_upload_id,
        'photo_id': photo_id,
        'confidence': confidence,
    }
    matches_col().insert_one(data)
    data.pop('_id', None)
    return data


def get_matches_by_guest(upload_id: int) -> list[dict]:
    return list(matches_col().find(
        {'guest_upload_id': upload_id},
        {'_id': 0},
    ).sort('confidence', DESCENDING))


def count_matches(upload_id: int) -> int:
    return matches_col().count_documents({'guest_upload_id': upload_id})


# Legacy compat aliases used by old tasks.py / agent_api.py
def upsert_photo(photo_id: int, data: dict):
    update_photo(photo_id, data)

def upsert_guest(upload_id: int, data: dict):
    update_guest(upload_id, data)

def insert_match(upload_id: int, photo_id: int, confidence: float):
    create_or_update_match(upload_id, photo_id, confidence)
