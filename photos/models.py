"""
EventPhoto model — MongoDB-backed, no Django ORM.
"""

import os
from datetime import datetime
from pathlib import Path
from django.conf import settings
import mongo_store
from events.models import BoundFileRef


class _EventPhotoManager:
    def get(self, pk=None, **kwargs):
        if pk is None:
            pk = kwargs.get('id') or kwargs.get('pk')
        doc = mongo_store.get_photo_by_id(pk)
        if not doc:
            raise EventPhoto.DoesNotExist
        return EventPhoto(doc)

    def create(self, event, image, **kwargs):
        from pathlib import Path
        import time
        folder = Path(settings.MEDIA_ROOT) / 'event_photos' / event.slug
        folder.mkdir(parents=True, exist_ok=True)
        original = image.name or 'photo.jpg'
        stem = Path(original).stem
        ext = Path(original).suffix or '.jpg'
        unique = f'{stem}_{int(time.time() * 1000)}{ext}'
        dest = folder / unique
        with open(dest, 'wb') as fh:
            for chunk in image.chunks():
                fh.write(chunk)
        rel = f'event_photos/{event.slug}/{unique}'
        doc = mongo_store.create_photo({
            'event_id': event.pk,
            'event_slug': event.slug,
            'image': rel,
            'thumbnail': '',
        })
        return EventPhoto(doc)

    def filter(self, **kwargs):
        event_id = kwargs.get('event_id')
        processed = kwargs.get('processed')
        if event_id is not None:
            docs = mongo_store.get_photos_by_event(event_id)
        else:
            event = kwargs.get('event')
            if event is not None:
                docs = mongo_store.get_photos_by_event(event.pk)
            else:
                docs = []
        if processed is not None:
            docs = [d for d in docs if d.get('processed') == processed]
        return _PhotoQuerySet([EventPhoto(d) for d in docs])

    def get_or_create(self, defaults=None, **kwargs):
        try:
            obj = self.get(**kwargs)
            return obj, False
        except EventPhoto.DoesNotExist:
            params = {**(defaults or {}), **kwargs}
            return self.create(**params), True


class _PhotoQuerySet:
    def __init__(self, items):
        self._items = items

    def __iter__(self):     return iter(self._items)
    def __len__(self):      return len(self._items)
    def __bool__(self):     return bool(self._items)
    def count(self):        return len(self._items)
    def exists(self):       return bool(self._items)
    def order_by(self, *a): return self
    def filter(self, **kw): return self
    def exclude(self, **kw):return self
    def __getitem__(self, idx): return self._items[idx]

    def values(self, *fields):
        if not fields:
            return [p.__dict__ for p in self._items]
        return [{f: getattr(p, f, None) for f in fields} for p in self._items]


class EventPhoto:
    DoesNotExist = type('DoesNotExist', (Exception,), {})
    objects = _EventPhotoManager()

    def __init__(self, doc: dict):
        self.pk = doc.get('id')
        self.id = doc.get('id')
        self.event_id = doc.get('event_id')
        self.event_slug = doc.get('event_slug', '')
        self._image_name = doc.get('image', '')
        self._thumbnail_name = doc.get('thumbnail', '')
        self.processed = doc.get('processed', False)
        self.face_count = doc.get('face_count', 0)
        self.uploaded_at = doc.get('uploaded_at', datetime.utcnow())
        self.face_encodings = doc.get('face_encodings', [])

    # ── file-field properties ─────────────────────────────────────────────

    @property
    def image(self):
        ref = BoundFileRef(self, 'image')
        ref.name = self._image_name
        return ref

    @property
    def thumbnail(self):
        ref = BoundFileRef(self, 'thumbnail')
        ref.name = self._thumbnail_name
        return ref

    def _mongo_save_field(self, field: str, value):
        mongo_store.update_photo(self.pk, {field: value})

    # ── convenience properties ────────────────────────────────────────────

    @property
    def filename(self):
        return os.path.basename(self._image_name)

    @property
    def event(self):
        from events.models import Event
        doc = mongo_store.get_event_by_id(self.event_id)
        return Event(doc) if doc else None

    # ── persistence ───────────────────────────────────────────────────────

    def save(self, update_fields=None):
        data = {
            'image': self._image_name,
            'thumbnail': self._thumbnail_name,
            'processed': self.processed,
            'face_count': self.face_count,
            'face_encodings': self.face_encodings,
        }
        if update_fields:
            data = {k: data[k] for k in update_fields if k in data}
        mongo_store.update_photo(self.pk, data)

    def delete(self):
        mongo_store.delete_photo(self.pk)

    def __str__(self):
        return f'Photo {self.pk} ({self.filename})'
