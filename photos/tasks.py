import logging
import io
from celery import shared_task
from django.conf import settings
from PIL import Image
from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_event_photo(self, photo_id: int):
    """Detect faces in an event photo; store encodings in MongoDB."""
    from photos.models import EventPhoto
    import mongo_store

    try:
        photo = EventPhoto.objects.get(pk=photo_id)
    except EventPhoto.DoesNotExist:
        return

    # Skip if already processed
    if photo.processed:
        return

    try:
        import face_recognition
        img = face_recognition.load_image_file(photo.image.path)
        encodings = face_recognition.face_encodings(img)
        encoding_list = [enc.tolist() for enc in encodings]
        face_count = len(encodings)
    except ImportError:
        logger.warning('face_recognition not installed — marking photo %s as processed', photo_id)
        encoding_list = []
        face_count = 0
    except Exception as exc:
        logger.exception('Error processing photo %s', photo_id)
        raise self.retry(exc=exc)

    mongo_store.upsert_photo(photo_id, {
        'event_id': photo.event_id,
        'image_path': photo.image.name,
        'face_encodings': encoding_list,
        'face_count': face_count,
        'processed': True,
    })

    photo.face_count = face_count
    photo.processed = True
    photo.save(update_fields=['face_count', 'processed'])
    logger.info('Photo %s processed: %d face(s)', photo_id, face_count)
