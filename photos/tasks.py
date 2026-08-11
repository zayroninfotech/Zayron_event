import logging
import io
from celery import shared_task
from django.conf import settings
from PIL import Image
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_event_photo(self, photo_id: int):
    """Detect faces in an event photo; store encodings in MongoDB."""
    try:
        import face_recognition
    except ImportError:
        logger.error('face_recognition not installed — skipping photo %s', photo_id)
        return

    from photos.models import EventPhoto
    import mongo_store

    try:
        photo = EventPhoto.objects.get(pk=photo_id)
    except EventPhoto.DoesNotExist:
        return

    try:
        img = face_recognition.load_image_file(photo.image.path)
        encodings = face_recognition.face_encodings(img)
        encoding_list = [enc.tolist() for enc in encodings]

        # Persist encodings + metadata to MongoDB
        mongo_store.upsert_photo(photo_id, {
            'event_id': photo.event_id,
            'image_path': photo.image.name,
            'face_encodings': encoding_list,
            'face_count': len(encodings),
            'processed': True,
        })

        # Update SQLite record (processed flag + face count for dashboard display)
        photo.face_count = len(encodings)
        photo.processed = True

        _make_thumbnail(photo)
        photo.save()

        logger.info('Photo %s processed: %d face(s)', photo_id, len(encodings))
    except Exception as exc:
        logger.exception('Error processing photo %s', photo_id)
        raise self.retry(exc=exc)


def _make_thumbnail(photo):
    thumb_size = getattr(settings, 'THUMBNAIL_SIZE', (400, 400))
    try:
        with Image.open(photo.image.path) as img:
            img.thumbnail(thumb_size, Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            photo.thumbnail.save(f'thumb_{photo.pk}.jpg', ContentFile(buf.getvalue()), save=False)
    except Exception:
        logger.exception('Thumbnail failed for photo %s', photo.pk)
