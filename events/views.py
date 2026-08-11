from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Event
from .forms import EventForm


@login_required
def dashboard(request):
    events = Event.objects.filter(created_by=request.user)
    return render(request, 'events/dashboard.html', {'events': events})


@login_required
def event_create(request):
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save(commit=False)
            event.created_by = request.user
            event.save()
            messages.success(request, f'Event "{event.name}" created!')
            return redirect('event_detail', slug=event.slug)
    else:
        form = EventForm()
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Create'})


@login_required
def event_detail(request, slug):
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
    photos = event.photos.all().order_by('-uploaded_at')
    return render(request, 'events/event_detail.html', {'event': event, 'photos': photos})


@login_required
def event_edit(request, slug):
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated.')
            return redirect('event_detail', slug=event.slug)
    else:
        form = EventForm(instance=event)
    return render(request, 'events/event_form.html', {'form': form, 'action': 'Edit', 'event': event})


@login_required
def event_delete(request, slug):
    event = get_object_or_404(Event, slug=slug, created_by=request.user)
    if request.method == 'POST':
        name = event.name
        event.delete()
        messages.success(request, f'Event "{name}" deleted.')
        return redirect('dashboard')
    return render(request, 'events/event_confirm_delete.html', {'event': event})
