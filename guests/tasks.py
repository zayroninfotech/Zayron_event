import logging
import numpy as np
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def match_guest_faces(self, guest_upload_id: int):
    """
    1. Generate face encoding from guest selfie.
    2. Compare against all processed EventPhoto encodings for the same event.
    3. Save PhotoMatch records for hits within tolerance.
    """
    try:
        import face_recognition
    except ImportError:
        logger.error('face_recognition not installed')
        return

    from guests.models import GuestUpload, PhotoMatch
    from photos.models import EventPhoto
    from django.conf import settings

    tolerance = getattr(settings, 'FACE_MATCH_TOLERANCE', 0.5)

    try:
        upload = GuestUpload.objects.get(pk=guest_upload_id)
    except GuestUpload.DoesNotExist:
        logger.warning('GuestUpload %s not found', guest_upload_id)
        return

    upload.status = 'processing'
    upload.save(update_fields=['status'])

    try:
        selfie_img = face_recognition.load_image_file(upload.selfie.path)
        selfie_encodings = face_recognition.face_encodings(selfie_img)

        if not selfie_encodings:
            logger.warning('No face found in selfie for guest_upload %s', guest_upload_id)
            upload.status = 'done'
            upload.save(update_fields=['status'])
            return

        guest_encoding = selfie_encodings[0]
        upload.face_encoding = guest_encoding.tolist()
        upload.save(update_fields=['face_encoding'])

        event_photos = EventPhoto.objects.filter(
            event=upload.event,
            processed=True,
        ).exclude(face_encodings=[])

        matches_created = 0
        for photo in event_photos:
            if not photo.face_encodings:
                continue

            known_encodings = [np.array(enc) for enc in photo.face_encodings]
            distances = face_recognition.face_distance(known_encodings, guest_encoding)

            if any(d <= tolerance for d in distances):
                best_distance = float(min(distances))
                PhotoMatch.objects.get_or_create(
                    guest_upload=upload,
                    photo=photo,
                    defaults={'confidence': best_distance},
                )
                matches_created += 1

        upload.status = 'done'
        upload.save(update_fields=['status'])
        logger.info('Guest %s: %d match(es) found', guest_upload_id, matches_created)

    except Exception as exc:
        logger.exception('Error matching guest %s', guest_upload_id)
        upload.status = 'failed'
        upload.save(update_fields=['status'])
        raise self.retry(exc=exc)
