from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_POST
import mongo_store
from .models import Event
from .forms import EventForm


def _get_event_or_404(slug, user=None):
    doc = mongo_store.get_event_by_slug(slug)
    if not doc:
        raise Http404
    if user and doc.get('created_by_id') != user.pk:
        raise Http404
    return Event(doc)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
def dashboard(request):
    events = Event.objects.filter(created_by=request.user)
    total_photos = sum(e.total_photos for e in events)
    total_searches = sum(e.guest_uploads.count() for e in events)
    return render(request, 'events/dashboard.html', {
        'events': events,
        'total_photos': total_photos,
        'total_searches': total_searches,
    })


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = Event.create(
                name=form.cleaned_data['name'],
                event_date=form.cleaned_data['event_date'],
                description=form.cleaned_data.get('description', ''),
                created_by_id=request.user.pk,
            )
            if _is_ajax(request):
                return JsonResponse({'slug': event.slug, 'name': event.name})
            messages.success(request, f'Event "{event.name}" created!')
            return redirect('event_detail', slug=event.slug)
        if _is_ajax(request):
            errors = {f: e.get_json_data() for f, e in form.errors.items()}
            return JsonResponse({'errors': errors}, status=400)
    else:
        form = EventForm()
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Create'})


@login_required
def event_detail(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    photos = event.photos.all()
    return render(request, 'events/event_detail.html', {'event': event, 'photos': photos})


@login_required
def event_edit(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event.name = form.cleaned_data['name']
            event.event_date = form.cleaned_data['event_date']
            event.description = form.cleaned_data.get('description', '')
            event.save(update_fields=['name', 'event_date', 'description'])
            messages.success(request, 'Event updated.')
            return redirect('event_detail', slug=event.slug)
    else:
        form = EventForm(initial={
            'name': event.name,
            'event_date': event.event_date,
            'description': event.description,
        })
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@login_required
@require_POST
def toggle_agent_sync(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    event.agent_sync_enabled = not event.agent_sync_enabled
    event.save(update_fields=['agent_sync_enabled'])
    return JsonResponse({'enabled': event.agent_sync_enabled})


@login_required
def event_delete(request, slug):
    event = _get_event_or_404(slug, user=request.user)
    if request.method == 'POST':
        name = event.name
        event.delete()
        messages.success(request, f'Event "{name}" deleted.')
        return redirect('dashboard')
    return render(request, 'events/event_confirm_delete.html', {'event': event})
