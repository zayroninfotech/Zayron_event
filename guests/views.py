import zipfile
import io
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.http import require_POST
from events.models import Event
from .models import GuestUpload, PhotoMatch
from .forms import GuestUploadForm
from .tasks import match_guest_faces
from photos.models import EventPhoto


def guest_landing(request, slug):
    return redirect('guest_upload', slug=slug)


def guest_upload(request, slug):
    event = get_object_or_404(Event, slug=slug)
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
            upload.task_id = task.id
            upload.save(update_fields=['task_id'])
            return redirect('guest_results', slug=slug, upload_id=upload.pk)
    else:
        form = GuestUploadForm()
    return render(request, 'guests/upload.html', {'event': event, 'form': form})


def guest_results(request, slug, upload_id):
    event = get_object_or_404(Event, slug=slug)
    upload = get_object_or_404(GuestUpload, pk=upload_id, event=event)
    matches = upload.matches.select_related('photo').order_by('confidence') if upload.status == 'done' else []
    return render(request, 'guests/results.html', {
        'event': event,
        'upload': upload,
        'matches': matches,
    })


def guest_status_api(request, upload_id):
    upload = get_object_or_404(GuestUpload, pk=upload_id)
    terminal = upload.status in ('done', 'no_face', 'failed')
    return JsonResponse({
        'status': upload.status,
        'match_count': upload.matches.count() if upload.status == 'done' else None,
        'terminal': terminal,
    })


def download_photo(request, slug, photo_id):
    event = get_object_or_404(Event, slug=slug)
    photo = get_object_or_404(EventPhoto, pk=photo_id, event=event)
    response = FileResponse(open(photo.image.path, 'rb'), as_attachment=True)
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(photo.image.name)}"'
    return response


def download_zip(request, slug, upload_id):
    event = get_object_or_404(Event, slug=slug)
    upload = get_object_or_404(GuestUpload, pk=upload_id, event=event)
    matches = upload.matches.select_related('photo').filter(photo__image__isnull=False)

    if not matches.exists():
        raise Http404('No matched photos to download.')

    def zip_generator():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            for match in matches:
                try:
                    photo_path = match.photo.image.path
                    arcname = os.path.basename(photo_path)
                    zf.write(photo_path, arcname)
                except FileNotFoundError:
                    continue
        buf.seek(0)
        return buf.read()

    zip_bytes = zip_generator()
    response = FileResponse(
        io.BytesIO(zip_bytes),
        as_attachment=True,
        filename=f'{event.slug}_my_photos.zip',
        content_type='application/zip',
    )
    return response
