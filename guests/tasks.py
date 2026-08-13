import logging
import cv2
import numpy as np
from celery import shared_task

logger = logging.getLogger(__name__)

_face_app = None

SIMILARITY_THRESHOLD = 0.40


def _get_face_app():
    global _face_app
    if _face_app is None:
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))
    return _face_app


def _cosine_similarity(a, b):
    a, b = np.array(a), np.array(b)
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def match_guest_faces(self, guest_upload_id: int):
    """
    1. Generate ArcFace embedding from guest selfie.
    2. Compare against all event photo embeddings in MongoDB.
    3. Save PhotoMatch records for matches above threshold.
    """
    try:
        import insightface  # noqa
        HAS_INSIGHTFACE = True
    except ImportError:
        logger.warning('insightface not installed — returning all event photos as fallback')
        HAS_INSIGHTFACE = False

    from guests.models import GuestUpload, PhotoMatch
    from photos.models import EventPhoto
    import mongo_store

    try:
        upload = GuestUpload.objects.get(pk=guest_upload_id)
    except GuestUpload.DoesNotExist:
        return

    upload.status = 'processing'
    upload.save(update_fields=['status'])

    try:
        # ── Fallback: no insightface → show all event photos ──────────────
        if not HAS_INSIGHTFACE:
            for doc in mongo_store.get_photos_by_event(upload.event_id):
                photo = EventPhoto(doc)
                mongo_store.create_or_update_match(guest_upload_id, photo.pk, 0.0)
            upload.status = 'done'
            upload.save(update_fields=['status'])
            return

        # ── Load selfie and get ArcFace embedding ─────────────────────────
        app = _get_face_app()
        selfie_img = cv2.imread(upload.selfie.path)
        if selfie_img is None:
            raise ValueError('Cannot read selfie image')

        faces = app.get(selfie_img)
        if not faces:
            upload.status = 'no_face'
            upload.save(update_fields=['status'])
            mongo_store.update_guest(guest_upload_id, {'status': 'no_face', 'face_encoding': []})
            return

        guest_face = max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))
        guest_emb = guest_face.embedding.tolist()

        mongo_store.update_guest(guest_upload_id, {
            'face_encoding': guest_emb,
            'status': 'processing',
        })

        # ── Compare against all event photo embeddings ─────────────────────
        photo_docs = mongo_store.get_event_photo_encodings(upload.event_id)
        matches_created = 0

        for doc in photo_docs:
            if not doc.get('face_encodings'):
                continue
            best_sim = max(
                _cosine_similarity(guest_emb, enc)
                for enc in doc['face_encodings']
            )
            if best_sim >= SIMILARITY_THRESHOLD:
                photo_id = doc['id']
                mongo_store.create_or_update_match(guest_upload_id, photo_id, best_sim)
                matches_created += 1

        upload.status = 'done'
        upload.save(update_fields=['status'])
        mongo_store.update_guest(guest_upload_id, {'status': 'done'})
        logger.info('Guest %s: %d match(es)', guest_upload_id, matches_created)

    except Exception as exc:
        logger.exception('Error matching guest %s', guest_upload_id)
        upload.status = 'failed'
        upload.save(update_fields=['status'])
        mongo_store.update_guest(guest_upload_id, {'status': 'failed'})
        raise self.retry(exc=exc)
