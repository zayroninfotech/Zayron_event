"""
Event model — MongoDB-backed, no Django ORM.
Provides an ORM-like interface so existing views/templates work unchanged.
"""

import io
import os
import qrcode
from datetime import datetime
from pathlib import Path
from django.utils.text import slugify
from django.conf import settings
from django.urls import reverse
import mongo_store


class BoundFileRef:
    """
    Mimics Django's FieldFile so templates can use .url/.path and
    views can call .save() / .delete() just like an ImageField.
    """

    def __init__(self, obj, field: str):
        self._obj = obj
        self._field = field
        self.name = getattr(obj, f'_{field}_name', '') or ''

    # ── read-only helpers ─────────────────────────────────────────────────

    @property
    def url(self):
        return (settings.MEDIA_URL + self.name) if self.name else ''

    @property
    def path(self):
        return str(Path(settings.MEDIA_ROOT) / self.name) if self.name else ''

    def __bool__(self):
        return bool(self.name)

    def __str__(self):
        return self.name

    # ── write helpers ─────────────────────────────────────────────────────

    def save(self, upload_name: str, content, save: bool = True):
        folder = 'thumbnails' if self._field == 'thumbnail' else 'uploads'
        stored_name = f'{folder}/{upload_name}'
        p = Path(settings.MEDIA_ROOT) / stored_name
        p.parent.mkdir(parents=True, exist_ok=True)
        data = content.read() if hasattr(content, 'read') else bytes(content)
        with open(p, 'wb') as fh:
            fh.write(data)
        self.name = stored_name
        setattr(self._obj, f'_{self._field}_name', stored_name)
        if save:
            self._obj._mongo_save_field(self._field, stored_name)

    def delete(self, save: bool = True):
        if self.name and os.path.exists(self.path):
            try:
                os.remove(self.path)
            except Exception:
                pass
        self.name = ''
        setattr(self._obj, f'_{self._field}_name', '')
        if save:
            self._obj._mongo_save_field(self._field, '')


# ── Related managers ──────────────────────────────────────────────────────

class _EventPhotoRelated:
    def __init__(self, event_id, event_slug=''):
        self.event_id = event_id
        self._slug = event_slug

    def all(self):
        from photos.models import EventPhoto
        return [EventPhoto(d) for d in mongo_store.get_photos_by_event(self.event_id)]

    def last(self):
        from photos.models import EventPhoto
        doc = mongo_store.get_last_photo(self.event_id)
        return EventPhoto(doc) if doc else None

    def count(self):
        return mongo_store.count_photos(self.event_id)

    def filter(self, **kwargs):
        from photos.models import EventPhoto
        docs = mongo_store.get_photos_by_event(self.event_id)
        for k, v in kwargs.items():
            if k == 'processed':
                docs = [d for d in docs if d.get('processed') == v]
            elif k == 'image__isnull':
                docs = [d for d in docs if (not d.get('image')) == v]
        return _PhotoQuerySet([EventPhoto(d) for d in docs])

    def values(self, *fields):
        return mongo_store.get_photos_values(self.event_id)

    def order_by(self, field):
        return self.all()

    def exists(self):
        return self.count() > 0


class _PhotoQuerySet:
    def __init__(self, items):
        self._items = items

    def __iter__(self):     return iter(self._items)
    def __len__(self):      return len(self._items)
    def __bool__(self):     return bool(self._items)
    def count(self):        return len(self._items)
    def exists(self):       return bool(self._items)
    def order_by(self, f):  return self
    def filter(self, **kw): return self
    def exclude(self, **kw):return self


class _GuestRelated:
    def __init__(self, event_id):
        self.event_id = event_id

    def count(self):
        return mongo_store.count_guests(self.event_id)

    def all(self):
        from guests.models import GuestUpload
        return [GuestUpload(d) for d in mongo_store.get_guests_by_event(self.event_id)]

    def filter(self, **kwargs):
        return self.all()


# ── Manager ───────────────────────────────────────────────────────────────

class _EventManager:
    def filter(self, **kwargs):
        user = kwargs.pop('created_by', None)
        if user is not None:
            docs = mongo_store.get_events_by_user(user.pk)
        elif 'created_by_id' in kwargs:
            docs = mongo_store.get_events_by_user(kwargs.pop('created_by_id'))
        else:
            docs = list(mongo_store.events_col().find({}, {'_id': 0}).sort('created_at', -1))
        slug = kwargs.get('slug')
        if slug:
            docs = [d for d in docs if d.get('slug') == slug]
        return _EventQuerySet([Event(d) for d in docs])

    def get(self, **kwargs):
        user = kwargs.pop('created_by', None)
        uid = user.pk if user else None
        slug = kwargs.get('slug')
        id_ = kwargs.get('id') or kwargs.get('pk')
        if slug:
            doc = mongo_store.get_event_by_slug(slug)
        elif id_:
            doc = mongo_store.get_event_by_id(id_)
        else:
            doc = None
        if not doc:
            raise Event.DoesNotExist
        if uid and doc.get('created_by_id') != uid:
            raise Event.DoesNotExist
        return Event(doc)

    def create(self, **kwargs):
        return Event.create(**kwargs)

    def count(self):
        return mongo_store.events_col().count_documents({})

    def all(self):
        return _EventQuerySet([Event(d) for d in mongo_store.events_col().find({}, {'_id': 0}).sort('created_at', -1)])

    def order_by(self, *args):
        return self.all()

    def __iter__(self):
        return iter(self.all())


class _EventQuerySet:
    def __init__(self, items):
        self._items = items

    def __iter__(self):     return iter(self._items)
    def __len__(self):      return len(self._items)
    def __bool__(self):     return bool(self._items)
    def count(self):        return len(self._items)
    def exists(self):       return bool(self._items)
    def order_by(self, *a): return self
    def filter(self, **kw): return self

    def __getitem__(self, idx):
        return self._items[idx]


# ── Event ─────────────────────────────────────────────────────────────────

class Event:
    DoesNotExist = type('DoesNotExist', (Exception,), {})
    objects = _EventManager()

    def __init__(self, doc: dict):
        self.pk = doc.get('id')
        self.id = doc.get('id')
        self.name = doc.get('name', '')
        self.slug = doc.get('slug', '')
        self.created_by_id = doc.get('created_by_id')
        self.event_date = doc.get('event_date', '')
        self.description = doc.get('description', '')
        self.watch_folder = doc.get('watch_folder', '')
        self.agent_sync_enabled = doc.get('agent_sync_enabled', False)
        self.created_at = doc.get('created_at')
        self._qr_code_name = doc.get('qr_code', '')
        self.qr_code = BoundFileRef(self, 'qr_code')
        self.qr_code.name = self._qr_code_name

    # ── properties ────────────────────────────────────────────────────────

    @property
    def photos(self):
        return _EventPhotoRelated(self.pk, self.slug)

    @property
    def guest_uploads(self):
        return _GuestRelated(self.pk)

    @property
    def total_photos(self):
        return mongo_store.count_photos(self.pk)

    @property
    def processed_photos(self):
        return mongo_store.count_processed_photos(self.pk)

    # ── persistence ───────────────────────────────────────────────────────

    def _mongo_save_field(self, field: str, value):
        mongo_store.update_event(self.pk, {field: value})

    def save(self, update_fields=None):
        data = {
            'name': self.name,
            'slug': self.slug,
            'created_by_id': self.created_by_id,
            'event_date': str(self.event_date),
            'description': self.description,
            'watch_folder': self.watch_folder,
            'agent_sync_enabled': self.agent_sync_enabled,
            'qr_code': self._qr_code_name,
        }
        if update_fields:
            data = {k: data[k] for k in update_fields if k in data}
        mongo_store.update_event(self.pk, data)

    def delete(self):
        if self._qr_code_name:
            try:
                os.remove(str(Path(settings.MEDIA_ROOT) / self._qr_code_name))
            except Exception:
                pass
        mongo_store.delete_event(self.pk)

    # ── class method factory ──────────────────────────────────────────────

    @classmethod
    def create(cls, name, event_date, description='', watch_folder='',
               created_by=None, created_by_id=None, **kwargs):
        base_slug = slugify(f"{name} {event_date}")
        slug = base_slug
        n = 1
        while mongo_store.get_event_by_slug(slug):
            slug = f'{base_slug}-{n}'
            n += 1

        uid = created_by_id or (created_by.pk if created_by else None)
        doc = mongo_store.create_event({
            'name': name,
            'slug': slug,
            'created_by_id': uid,
            'event_date': str(event_date),
            'description': description,
            'watch_folder': watch_folder,
        })
        event = cls(doc)
        event._generate_qr_code()
        return event

    def _generate_qr_code(self):
        guest_url = reverse('guest_landing', kwargs={'slug': self.slug})
        site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
        full_url = f'{site_url}{guest_url}'
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        qr_name = f'qr_codes/{self.slug}/qr_{self.slug}.png'
        p = Path(settings.MEDIA_ROOT) / qr_name
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, 'wb') as fh:
            fh.write(buf.getvalue())
        self._qr_code_name = qr_name
        self.qr_code = BoundFileRef(self, 'qr_code')
        self.qr_code.name = qr_name
        mongo_store.update_event(self.pk, {'qr_code': qr_name})

    def __str__(self):
        return self.name
