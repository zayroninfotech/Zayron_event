"""
GuestUpload and PhotoMatch models — MongoDB-backed, no Django ORM.
"""

import os
from datetime import datetime
from pathlib import Path
from django.conf import settings
import mongo_store
from events.models import BoundFileRef


# ── PhotoMatch ────────────────────────────────────────────────────────────

class _PhotoMatchManager:
    def get_or_create(self, defaults=None, **kwargs):
        guest_upload = kwargs.get('guest_upload')
        photo = kwargs.get('photo')
        if guest_upload and photo:
            doc = mongo_store.matches_col().find_one(
                {'guest_upload_id': guest_upload.pk, 'photo_id': photo.pk},
                {'_id': 0},
            )
            if doc:
                return PhotoMatch(doc), False
            data = {**(defaults or {})}
            confidence = data.get('confidence', 0.0)
            doc = mongo_store.create_or_update_match(guest_upload.pk, photo.pk, confidence)
            return PhotoMatch(doc), True
        raise ValueError('guest_upload and photo required')


class PhotoMatch:
    DoesNotExist = type('DoesNotExist', (Exception,), {})
    objects = _PhotoMatchManager()

    def __init__(self, doc: dict):
        self.pk = doc.get('id')
        self.id = doc.get('id')
        self.guest_upload_id = doc.get('guest_upload_id')
        self.photo_id = doc.get('photo_id')
        self.confidence = doc.get('confidence', 0.0)
        self._photo_cache = None

    @property
    def photo(self):
        if self._photo_cache is None:
            from photos.models import EventPhoto
            doc = mongo_store.get_photo_by_id(self.photo_id)
            self._photo_cache = EventPhoto(doc) if doc else None
        return self._photo_cache

    def __str__(self):
        return f'Match guest={self.guest_upload_id} photo={self.photo_id} sim={self.confidence:.3f}'


# ── Related managers ──────────────────────────────────────────────────────

class _MatchRelated:
    def __init__(self, upload_id):
        self._upload_id = upload_id

    def count(self):
        return mongo_store.count_matches(self._upload_id)

    def all(self):
        return [PhotoMatch(d) for d in mongo_store.get_matches_by_guest(self._upload_id)]

    def select_related(self, *args):
        return _MatchQuerySet(self.all())

    def order_by(self, field):
        items = self.all()
        rev = field.startswith('-')
        key = field.lstrip('-')
        items.sort(key=lambda m: getattr(m, key, 0), reverse=rev)
        return _MatchQuerySet(items)

    def filter(self, **kwargs):
        return _MatchQuerySet(self.all())

    def exists(self):
        return self.count() > 0


class _MatchQuerySet:
    def __init__(self, items):
        self._items = items

    def __iter__(self):     return iter(self._items)
    def __len__(self):      return len(self._items)
    def __bool__(self):     return bool(self._items)
    def count(self):        return len(self._items)
    def exists(self):       return bool(self._items)
    def order_by(self, *a): return self
    def filter(self, **kw): return self
    def select_related(self, *a): return self
    def __getitem__(self, idx): return self._items[idx]


# ── GuestUpload manager ───────────────────────────────────────────────────

class _GuestUploadManager:
    def get(self, pk=None, **kwargs):
        if pk is None:
            pk = kwargs.get('id') or kwargs.get('pk')
        # Support event= filter
        doc = mongo_store.get_guest_by_id(pk)
        if not doc:
            raise GuestUpload.DoesNotExist
        event = kwargs.get('event')
        if event and doc.get('event_id') != event.pk:
            raise GuestUpload.DoesNotExist
        return GuestUpload(doc)

    def create(self, event, selfie, name='', phone='', status='pending', **kwargs):
        import time
        folder = Path(settings.MEDIA_ROOT) / 'selfies' / event.slug
        folder.mkdir(parents=True, exist_ok=True)
        original = selfie.name or 'selfie.jpg'
        stem = Path(original).stem
        ext = Path(original).suffix or '.jpg'
        unique = f'{stem}_{int(time.time() * 1000)}{ext}'
        dest = folder / unique
        with open(dest, 'wb') as fh:
            for chunk in selfie.chunks():
                fh.write(chunk)
        rel = f'selfies/{event.slug}/{unique}'
        doc = mongo_store.create_guest({
            'event_id': event.pk,
            'selfie': rel,
            'name': name,
            'phone': phone,
            'status': status,
        })
        return GuestUpload(doc)

    def filter(self, **kwargs):
        event = kwargs.get('event')
        event_id = kwargs.get('event_id') or (event.pk if event else None)
        if event_id:
            docs = mongo_store.get_guests_by_event(event_id)
        else:
            event_ids = kwargs.get('event__in')
            if event_ids:
                event_ids_pks = [e.pk if hasattr(e, 'pk') else e for e in event_ids]
                docs = list(mongo_store.guests_col().find(
                    {'event_id': {'$in': event_ids_pks}}, {'_id': 0}
                ))
            else:
                docs = []
        return _GuestQuerySet([GuestUpload(d) for d in docs])

    def count(self):
        return mongo_store.guests_col().count_documents({})


class _GuestQuerySet:
    def __init__(self, items):
        self._items = items

    def __iter__(self):     return iter(self._items)
    def __len__(self):      return len(self._items)
    def __bool__(self):     return bool(self._items)
    def count(self):        return len(self._items)
    def exists(self):       return bool(self._items)
    def order_by(self, *a): return self
    def filter(self, **kw): return self


# ── GuestUpload ───────────────────────────────────────────────────────────

class GuestUpload:
    DoesNotExist = type('DoesNotExist', (Exception,), {})
    objects = _GuestUploadManager()

    def __init__(self, doc: dict):
        self.pk = doc.get('id')
        self.id = doc.get('id')
        self.event_id = doc.get('event_id')
        self._selfie_name = doc.get('selfie', '')
        self.name = doc.get('name', '')
        self.phone = doc.get('phone', '')
        self.task_id = doc.get('task_id', '')
        self.status = doc.get('status', 'pending')
        self.created_at = doc.get('created_at', datetime.utcnow())
        self.face_encoding = doc.get('face_encoding', [])

    @property
    def selfie(self):
        ref = BoundFileRef(self, 'selfie')
        ref.name = self._selfie_name
        return ref

    def _mongo_save_field(self, field: str, value):
        mongo_store.update_guest(self.pk, {field: value})

    @property
    def matches(self):
        return _MatchRelated(self.pk)

    @property
    def event(self):
        from events.models import Event
        doc = mongo_store.get_event_by_id(self.event_id)
        return Event(doc) if doc else None

    def save(self, update_fields=None):
        data = {
            'selfie': self._selfie_name,
            'name': self.name,
            'phone': self.phone,
            'task_id': self.task_id,
            'status': self.status,
            'face_encoding': self.face_encoding,
        }
        if update_fields:
            data = {k: data[k] for k in update_fields if k in data}
        mongo_store.update_guest(self.pk, data)

    def delete(self):
        mongo_store.guests_col().delete_one({'id': self.pk})
        mongo_store.matches_col().delete_many({'guest_upload_id': self.pk})

    def __str__(self):
        return f'GuestUpload {self.pk} ({self.name or "anonymous"})'
