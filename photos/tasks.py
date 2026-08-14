import logging
import cv2
import numpy as np
from celery import shared_task

logger = logging.getLogger(__name__)

_face_app = None


def _get_face_app():
    global _face_app
    if _face_app is None:
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

    if not photo._thumbnail_name:
        try:
            import io as _io
            from PIL import Image as _Image
            import pathlib, django.conf
            with _Image.open(photo.image.path) as img:
                img.thumbnail((400, 400), _Image.LANCZOS)
                buf = _io.BytesIO()
                img.save(buf, format='JPEG', quality=80)
                thumb_name = f'event_photos/{photo.event_slug}/thumbs/thumb_{photo.pk}.jpg'
                thumb_path = pathlib.Path(django.conf.settings.MEDIA_ROOT) / thumb_name
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                thumb_path.write_bytes(buf.getvalue())
                mongo_store.update_photo(photo_id, {'thumbnail': thumb_name})
        except Exception:
            pass

    if photo.processed:
        return

    try:
        import insightface  # noqa
    except ImportError:
        logger.warning('insightface not installed — marking photo %s as processed', photo_id)
        mongo_store.update_photo(photo_id, {
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

    mongo_store.update_photo(photo_id, {
        'face_encodings': embeddings,
        'face_count': face_count,
        'processed': True,
    })

    photo.face_count = face_count
    photo.processed = True
    photo.save(update_fields=['face_count', 'processed'])
    logger.info('Photo %s processed: %d face(s)', photo_id, face_count)
