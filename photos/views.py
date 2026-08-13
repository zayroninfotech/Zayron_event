import io
import os
import zipfile
from PIL import Image
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
import mongo_store
from events.models import Event
from events.views import _get_event_or_404
from .models import EventPhoto
from .tasks import process_event_photo


def _get_photo_or_404(photo_id, user=None):
    doc = mongo_store.get_photo_by_id(photo_id)
    if not doc:
        raise Http404
    if user:
        event_doc = mongo_store.get_event_by_id(doc.get('event_id'))
        if not event_doc or event_doc.get('created_by_id') != user.pk:
            raise Http404
    return EventPhoto(doc)


def _make_thumbnail_safe(photo):
    """Generate thumbnail and persist to MongoDB."""
    try:
        with Image.open(photo.image.path) as img:
            img.thumbnail((400, 400), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            thumb_name = f'event_photos/{photo.event_slug}/thumbs/thumb_{photo.pk}.jpg'
            thumb_path = __import__('pathlib').Path(
                __import__('django.conf', fromlist=['settings']).settings.MEDIA_ROOT
            ) / thumb_name
            thumb_path.parent.mkdir(parents=True, exist_ok=True)
            with open(thumb_path, 'wb') as fh:
                fh.write(buf.getvalue())
            photo._thumbnail_name = thumb_name
            mongo_store.update_photo(photo.pk, {'thumbnail': thumb_name})
    except Exception:
        pass


@login_required
@require_POST
def bulk_upload(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    files = request.FILES.getlist('photos')
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not files:
        if is_ajax:
            return JsonResponse({'error': 'No files provided.'}, status=400)
        messages.warning(request, 'No files selected.')
        return redirect('event_detail', slug=slug)

    created = []
    for f in files:
        photo = EventPhoto.objects.create(event=event, image=f)
        _make_thumbnail_safe(photo)
        created.append(photo.pk)
        process_event_photo.apply_async((photo.pk,), countdown=2)

    if is_ajax:
        photos_data = []
        for photo in [EventPhoto(mongo_store.get_photo_by_id(pid)) for pid in created]:
            photos_data.append({
                'id': photo.pk,
                'image_url': photo.image.url if photo._image_name else '',
                'thumbnail_url': photo.thumbnail.url if photo._thumbnail_name else '',
                'filename': photo.filename,
                'processed': photo.processed,
                'face_count': photo.face_count,
            })
        return JsonResponse({'uploaded': len(created), 'photos': photos_data})
    messages.success(request, f'{len(created)} photo(s) uploaded and queued for processing.')
    return redirect('event_detail', slug=slug)


@login_required
def photo_status(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    photos = event.photos.values('id', 'processed', 'face_count', 'uploaded_at')
    return JsonResponse({
        'total': event.total_photos,
        'processed': event.processed_photos,
        'photos': [
            {
                'id': p.get('id'),
                'processed': p.get('processed'),
                'face_count': p.get('face_count'),
                'uploaded_at': str(p.get('uploaded_at', '')),
            }
            for p in photos
        ],
    })


@login_required
def download_photo(request, photo_id):
    photo = _get_photo_or_404(photo_id, user=request.user)
    if not photo._image_name:
        raise Http404('Photo file not found.')
    response = FileResponse(open(photo.image.path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(photo._image_name)}"'
    return response


@login_required
def download_all_photos(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    photos = [p for p in event.photos.all() if p._image_name]

    if not photos:
        raise Http404('No photos to download.')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for photo in photos:
            try:
                zf.write(photo.image.path, os.path.basename(photo._image_name))
            except FileNotFoundError:
                continue
    buf.seek(0)
    return FileResponse(
        buf,
        as_attachment=True,
        filename=f'{event.slug}_photos.zip',
        content_type='application/zip',
    )


@login_required
@require_POST
def bulk_delete_photos(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    import json
    try:
        ids = json.loads(request.body).get('photo_ids', [])
    except Exception:
        return JsonResponse({'error': 'Invalid request'}, status=400)

    deleted = 0
    for photo_id in ids:
        doc = mongo_store.get_photo_by_id(int(photo_id))
        if not doc or doc.get('event_id') != event.pk:
            continue
        photo = EventPhoto(doc)
        try:
            if photo._image_name:
                photo.image.delete(save=False)
            if photo._thumbnail_name:
                photo.thumbnail.delete(save=False)
        except Exception:
            pass
        photo.delete()
        deleted += 1

    return JsonResponse({'deleted': deleted})


@login_required
@require_POST
def delete_photo(request, photo_id):
    photo = _get_photo_or_404(photo_id, user=request.user)
    slug = photo.event_slug or (photo.event.slug if photo.event else '')
    try:
        if photo._image_name:
            photo.image.delete(save=False)
        if photo._thumbnail_name:
            photo.thumbnail.delete(save=False)
    except Exception:
        pass
    photo.delete()
    messages.success(request, 'Photo deleted.')
    return redirect('event_detail', slug=slug)
