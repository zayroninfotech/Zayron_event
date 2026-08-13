import zipfile
import io
import os
from django.shortcuts import render, redirect
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_POST
import mongo_store
from events.models import Event
from .models import GuestUpload, PhotoMatch
from .forms import GuestUploadForm
from .tasks import match_guest_faces
from photos.models import EventPhoto


def _get_event_or_404(slug):
    doc = mongo_store.get_event_by_slug(slug)
    if not doc:
        raise Http404
    return Event(doc)


def _get_guest_or_404(upload_id, event=None):
    doc = mongo_store.get_guest_by_id(upload_id)
    if not doc:
        raise Http404
    if event and doc.get('event_id') != event.pk:
        raise Http404
    return GuestUpload(doc)


def guest_landing(request, slug):
    return redirect('guest_upload', slug=slug)


def guest_upload(request, slug):
    event = _get_event_or_404(slug)
    if request.method == 'POST':
        form = GuestUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = GuestUpload.objects.create(
                event=event,
                selfie=form.cleaned_data['selfie'],
                name=form.cleaned_data.get('name', ''),
                phone=form.cleaned_data.get('phone', ''),
                status='pending',
            )
            task = match_guest_faces.delay(upload.pk)
            upload.task_id = str(task.id)
            upload.save(update_fields=['task_id'])
            return redirect('guest_results', slug=slug, upload_id=upload.pk)
    else:
        form = GuestUploadForm()
    return render(request, 'guests/upload.html', {'event': event, 'form': form})


def guest_results(request, slug, upload_id):
    event = _get_event_or_404(slug)
    upload = _get_guest_or_404(upload_id, event=event)
    matches = upload.matches.select_related('photo').order_by('-confidence') if upload.status == 'done' else []
    return render(request, 'guests/results.html', {
        'event': event,
        'upload': upload,
        'matches': matches,
    })


def guest_status_api(request, upload_id):
    doc = mongo_store.get_guest_by_id(upload_id)
    if not doc:
        raise Http404
    upload = GuestUpload(doc)
    terminal = upload.status in ('done', 'no_face', 'failed')
    return JsonResponse({
        'status': upload.status,
        'match_count': mongo_store.count_matches(upload.pk) if upload.status == 'done' else None,
        'terminal': terminal,
    })


def download_photo(request, slug, photo_id):
    event = _get_event_or_404(slug)
    doc = mongo_store.get_photo_by_id(photo_id)
    if not doc or doc.get('event_id') != event.pk:
        raise Http404
    photo = EventPhoto(doc)
    if not photo._image_name:
        raise Http404
    response = FileResponse(open(photo.image.path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(photo._image_name)}"'
    return response


def download_zip(request, slug, upload_id):
    event = _get_event_or_404(slug)
    upload = _get_guest_or_404(upload_id, event=event)
    if upload.status != 'done':
        raise Http404('No matched photos yet.')

    match_docs = mongo_store.get_matches_by_guest(upload.pk)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for m in match_docs:
            photo_doc = mongo_store.get_photo_by_id(m.get('photo_id'))
            if not photo_doc or not photo_doc.get('image'):
                continue
            photo = EventPhoto(photo_doc)
            try:
                zf.write(photo.image.path, os.path.basename(photo._image_name))
            except FileNotFoundError:
                continue
    buf.seek(0)
    return FileResponse(
        buf,
        as_attachment=True,
        filename=f'{event.slug}_my_photos.zip',
        content_type='application/zip',
    )
