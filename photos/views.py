import io
import os
import zipfile
from PIL import Image
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from events.models import Event
from .models import EventPhoto
from .tasks import process_event_photo


def _make_thumbnail_safe(photo):
    """Fast thumbnail — uses Image.thumbnail so only needed pixels are decoded."""
    try:
        with Image.open(photo.image.path) as img:
            img.thumbnail((400, 400), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=80)
            photo.thumbnail.save(
                f'thumb_{photo.pk}.jpg',
                ContentFile(buf.getvalue()),
                save=True,
            )
    except Exception:
        pass


@login_required
@require_POST
def bulk_upload(request, slug):
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
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
        # Generate thumbnail immediately but lightweight — skip face recognition on upload
        _make_thumbnail_safe(photo)
        created.append(photo.pk)
        # Queue face recognition separately (runs after response is sent)
        process_event_photo.apply_async((photo.pk,), countdown=2)

    if is_ajax:
        return JsonResponse({'uploaded': len(created)})

    messages.success(request, f'{len(created)} photo(s) uploaded and queued for processing.')
    return redirect('event_detail', slug=slug)


@login_required
def photo_status(request, slug):
    """JSON endpoint for polling processing status."""
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
    photos = event.photos.values('id', 'processed', 'face_count', 'uploaded_at')
    return JsonResponse({
        'total': event.total_photos,
        'processed': event.processed_photos,
        'photos': list(photos),
    })


@login_required
def download_photo(request, photo_id):
    photo = get_object_or_404(EventPhoto, pk=photo_id, event__created_by=request.user)
    if not photo.image:
        raise Http404('Photo file not found.')
    response = FileResponse(open(photo.image.path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(photo.image.name)}"'
    return response


@login_required
def download_all_photos(request, slug):
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
    photos = event.photos.filter(image__isnull=False).exclude(image='')

    if not photos.exists():
        raise Http404('No photos to download.')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for photo in photos:
            try:
                zf.write(photo.image.path, os.path.basename(photo.image.name))
            except FileNotFoundError:
                continue
    buf.seek(0)

    response = FileResponse(
        buf,
        as_attachment=True,
        filename=f'{event.slug}_photos.zip',
        content_type='application/zip',
    )
    return response


@login_required
@require_POST
def delete_photo(request, photo_id):
    photo = get_object_or_404(EventPhoto, pk=photo_id, event__created_by=request.user)
    slug = photo.event.slug
    try:
        if photo.image:
            photo.image.delete(save=False)
        if photo.thumbnail:
            photo.thumbnail.delete(save=False)
    except Exception:
        pass
    photo.delete()
    messages.success(request, 'Photo deleted.')
    return redirect('event_detail', slug=slug)
