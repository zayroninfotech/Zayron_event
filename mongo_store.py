"""
MongoDB access layer (pymongo).

All face encodings, event metadata, guest uploads, and photo matches
are persisted in MongoDB. Django's SQLite DB is used only for auth,
sessions, admin, and celery infrastructure.

Collections:
  events          - mirrors events.Event (source of truth for event metadata)
  event_photos    - mirrors photos.EventPhoto (with face_encodings as BSON arrays)
  guest_uploads   - mirrors guests.GuestUpload (selfie metadata + face_encoding)
  photo_matches   - mirrors guests.PhotoMatch (guest → photo match results)
"""

from functools import lru_cache
from django.conf import settings
from pymongo import MongoClient
from pymongo.database import Database


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    host = settings.MONGO_HOST
    port = settings.MONGO_PORT
    user = settings.MONGO_USER
    password = settings.MONGO_PASSWORD
    auth_source = settings.MONGO_AUTH_SOURCE

    if user and password:
        return pymongo.MongoClient(
            host=host, port=port,
            username=user, password=password,
            authSource=auth_source,
        )
    return MongoClient(host=host, port=port)


def db() -> Database:
    return _client()[settings.MONGO_DB]


# ── convenience collection accessors ──────────────────────────────────────

def events_col():
    return db()['events']

def photos_col():
    return db()['event_photos']

def guests_col():
    return db()['guest_uploads']

def matches_col():
    return db()['photo_matches']


# ── Event ─────────────────────────────────────────────────────────────────

def upsert_event(event_id: int, data: dict):
    events_col().update_one(
        {'event_id': event_id},
        {'$set': {'event_id': event_id, **data}},
        upsert=True,
    )


def get_event(event_id: int) -> dict | None:
    return events_col().find_one({'event_id': event_id}, {'_id': 0})


# ── EventPhoto ─────────────────────────────────────────────────────────────

def upsert_photo(photo_id: int, data: dict):
    photos_col().update_one(
        {'photo_id': photo_id},
        {'$set': {'photo_id': photo_id, **data}},
        upsert=True,
    )


def get_photo_encodings(photo_id: int) -> list:
    doc = photos_col().find_one({'photo_id': photo_id}, {'face_encodings': 1})
    return doc.get('face_encodings', []) if doc else []


def get_event_photo_encodings(event_id: int) -> list[dict]:
    """Return list of {photo_id, face_encodings} for all processed photos in an event."""
    return list(photos_col().find(
        {'event_id': event_id, 'processed': True, 'face_encodings': {'$not': {'$size': 0}}},
        {'photo_id': 1, 'face_encodings': 1, '_id': 0},
    ))


# ── GuestUpload ────────────────────────────────────────────────────────────

def upsert_guest(upload_id: int, data: dict):
    guests_col().update_one(
        {'upload_id': upload_id},
        {'$set': {'upload_id': upload_id, **data}},
        upsert=True,
    )


def get_guest(upload_id: int) -> dict | None:
    return guests_col().find_one({'upload_id': upload_id}, {'_id': 0})


def delete_guest_biometric(upload_id: int):
    guests_col().update_one(
        {'upload_id': upload_id},
        {'$set': {'face_encoding': [], 'selfie_deleted': True}},
    )


# ── PhotoMatch ────────────────────────────────────────────────────────────

def insert_match(upload_id: int, photo_id: int, confidence: float):
    matches_col().update_one(
        {'upload_id': upload_id, 'photo_id': photo_id},
        {'$set': {'upload_id': upload_id, 'photo_id': photo_id, 'confidence': confidence}},
        upsert=True,
    )


def get_matches(upload_id: int) -> list[dict]:
    return list(matches_col().find(
        {'upload_id': upload_id},
        {'photo_id': 1, 'confidence': 1, '_id': 0},
    ).sort('confidence', 1))
