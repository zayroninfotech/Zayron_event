from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from events.models import Event
from .models import EventPhoto
from .tasks import process_event_photo


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
        process_event_photo.delay(photo.pk)
        created.append(photo.pk)

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
