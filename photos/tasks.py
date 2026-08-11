import logging
import cv2
import numpy as np
from celery import shared_task

logger = logging.getLogger(__name__)

_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
        import insightface
        from insightface.app import FaceAnalysis
        _face_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        _face_app.prepare(ctx_id=-1, det_size=(640, 640))
    return _face_app


@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def process_event_photo(self, photo_id: int):
    """Detect faces in an event photo using ArcFace; store embeddings in MongoDB."""
    from photos.models import EventPhoto
    import mongo_store

    try:
        photo = EventPhoto.objects.get(pk=photo_id)
    except EventPhoto.DoesNotExist:
        return

    if photo.processed:
        return

    try:
        import insightface  # noqa — check available
    except ImportError:
        logger.warning('insightface not installed — marking photo %s as processed', photo_id)
        mongo_store.upsert_photo(photo_id, {
            'event_id': photo.event_id,
            'image_path': photo.image.name,
            'face_encodings': [],
            'face_count': 0,
            'processed': True,
        })
        photo.face_count = 0
        photo.processed = True
        photo.save(update_fields=['face_count', 'processed'])
        return

    try:
        app = _get_face_app()
        img = cv2.imread(photo.image.path)
        if img is None:
            raise ValueError(f'Cannot read image: {photo.image.path}')

        # Resize large images to max 1920px to speed up detection
        h, w = img.shape[:2]
        if max(h, w) > 1920:
            scale = 1920 / max(h, w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)))

        faces = app.get(img)
        embeddings = [face.embedding.tolist() for face in faces]
        face_count = len(faces)

    except Exception as exc:
        logger.exception('Error processing photo %s', photo_id)
        raise self.retry(exc=exc)

    mongo_store.upsert_photo(photo_id, {
        'event_id': photo.event_id,
        'image_path': photo.image.name,
        'face_encodings': embeddings,
        'face_count': face_count,
        'processed': True,
    })

    photo.face_count = face_count
    photo.processed = True
    photo.save(update_fields=['face_count', 'processed'])
    logger.info('Photo %s processed: %d face(s)', photo_id, face_count)
