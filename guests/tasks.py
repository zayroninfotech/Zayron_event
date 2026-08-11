import logging
import numpy as np
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def match_guest_faces(self, guest_upload_id: int):
    """
    1. Generate face encoding from guest selfie.
    2. Compare against all event photo encodings stored in MongoDB.
    3. Save PhotoMatch records in both SQLite and MongoDB.
    """
    try:
        import face_recognition
    except ImportError:
        logger.error('face_recognition not installed')
        return

    from guests.models import GuestUpload, PhotoMatch
    from photos.models import EventPhoto
    from django.conf import settings
    import mongo_store

    tolerance = getattr(settings, 'FACE_MATCH_TOLERANCE', 0.5)

    try:
        upload = GuestUpload.objects.get(pk=guest_upload_id)
    except GuestUpload.DoesNotExist:
        return

    upload.status = 'processing'
    upload.save(update_fields=['status'])

    try:
        selfie_img = face_recognition.load_image_file(upload.selfie.path)
        selfie_encodings = face_recognition.face_encodings(selfie_img)

        if not selfie_encodings:
            upload.status = 'done'
            upload.save(update_fields=['status'])
            mongo_store.upsert_guest(guest_upload_id, {'status': 'done', 'face_encoding': []})
            return

        guest_enc = selfie_encodings[0]

        # Persist guest encoding to MongoDB
        mongo_store.upsert_guest(guest_upload_id, {
            'event_id': upload.event_id,
            'face_encoding': guest_enc.tolist(),
            'status': 'processing',
        })

        # Load all event photo encodings from MongoDB
        photo_docs = mongo_store.get_event_photo_encodings(upload.event_id)

        matches_created = 0
        for doc in photo_docs:
            if not doc.get('face_encodings'):
                continue

            known_encs = [np.array(e) for e in doc['face_encodings']]
            distances = face_recognition.face_distance(known_encs, guest_enc)

            if any(d <= tolerance for d in distances):
                best = float(min(distances))
                photo_id = doc['photo_id']

                # SQLite record for Django ORM queries
                try:
                    photo = EventPhoto.objects.get(pk=photo_id)
                    PhotoMatch.objects.get_or_create(
                        guest_upload=upload,
                        photo=photo,
                        defaults={'confidence': best},
                    )
                except EventPhoto.DoesNotExist:
                    pass

                # MongoDB record
                mongo_store.insert_match(guest_upload_id, photo_id, best)
                matches_created += 1

        upload.status = 'done'
        upload.save(update_fields=['status'])
        mongo_store.upsert_guest(guest_upload_id, {'status': 'done'})
        logger.info('Guest %s: %d match(es)', guest_upload_id, matches_created)

    except Exception as exc:
        logger.exception('Error matching guest %s', guest_upload_id)
        upload.status = 'failed'
        upload.save(update_fields=['status'])
        mongo_store.upsert_guest(guest_upload_id, {'status': 'failed'})
        raise self.retry(exc=exc)
