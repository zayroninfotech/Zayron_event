import logging
import numpy as np
from celery import shared_task
from django.conf import settings
from PIL import Image
import io
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_event_photo(self, photo_id: int):
    """Detect faces in an event photo and store encodings."""
    try:
        import face_recognition
    except ImportError:
        logger.error('face_recognition not installed — skipping encoding for photo %s', photo_id)
        return

    from photos.models import EventPhoto
    try:
        photo = EventPhoto.objects.get(pk=photo_id)
    except EventPhoto.DoesNotExist:
        logger.warning('EventPhoto %s not found', photo_id)
        return

    try:
        img = face_recognition.load_image_file(photo.image.path)
        encodings = face_recognition.face_encodings(img)
        photo.face_encodings = [enc.tolist() for enc in encodings]
        photo.face_count = len(encodings)
        photo.processed = True

        # Generate thumbnail
        _make_thumbnail(photo)

        photo.save()
        logger.info('Processed photo %s: %d face(s) found', photo_id, len(encodings))
    except Exception as exc:
        logger.exception('Error processing photo %s', photo_id)
        raise self.retry(exc=exc)


def _make_thumbnail(photo):
    thumb_size = getattr(settings, 'THUMBNAIL_SIZE', (400, 400))
    try:
        with Image.open(photo.image.path) as img:
            img.thumbnail(thumb_size, Image.LANCZOS)
            buf = io.BytesIO()
            fmt = img.format or 'JPEG'
            if fmt == 'JPG':
                fmt = 'JPEG'
            img.save(buf, format=fmt)
            thumb_name = f'thumb_{photo.pk}.jpg'
            photo.thumbnail.save(thumb_name, ContentFile(buf.getvalue()), save=False)
    except Exception:
        logger.exception('Thumbnail generation failed for photo %s', photo.pk)
