import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
import mongo_store
from events.models import Event
from photos.models import EventPhoto
from photos.tasks import process_event_photo


def _token_auth(request):
    auth = request.META.get('HTTP_AUTHORIZATION', '')
    if auth.startswith('Token '):
        try:
            return Token.objects.select_related('user').get(key=auth[6:]).user
        except Token.DoesNotExist:
            pass
    return None


@csrf_exempt
@require_http_methods(['POST'])
def agent_login(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    user = authenticate(username=data.get('username', ''), password=data.get('password', ''))
    if user is None:
        return JsonResponse({'error': 'Invalid credentials'}, status=401)
    token, _ = Token.objects.get_or_create(user=user)
    return JsonResponse({'token': token.key, 'username': user.username})


@csrf_exempt
@require_http_methods(['GET'])
def agent_events(request):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    events = Event.objects.filter(created_by=user)
    data = []
    for e in events:
        data.append({
            'id': e.id,
            'name': e.name,
            'slug': e.slug,
            'event_date': str(e.event_date),
            'description': e.description,
            'total_photos': e.total_photos,
            'processed_photos': e.processed_photos,
            'total_searches': mongo_store.count_guests(e.pk),
            'watch_folder': e.watch_folder,
            'agent_sync_enabled': e.agent_sync_enabled,
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(['POST'])
def agent_create_event(request):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    name = data.get('name', '').strip()
    event_date = data.get('event_date', '')
    description = data.get('description', '')
    if not name or not event_date:
        return JsonResponse({'error': 'name and event_date required'}, status=400)
    event = Event.create(
        name=name,
        event_date=event_date,
        description=description,
        created_by_id=user.pk,
    )
    return JsonResponse({'id': event.id, 'slug': event.slug, 'name': event.name}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def agent_upload_photo(request, slug):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    doc = mongo_store.get_event_by_slug(slug)
    if not doc or doc.get('created_by_id') != user.pk:
        return JsonResponse({'error': 'Event not found'}, status=404)
    event = Event(doc)
    photos_files = request.FILES.getlist('photos')
    if not photos_files:
        return JsonResponse({'error': 'No photos provided'}, status=400)
    saved = 0
    for f in photos_files:
        photo = EventPhoto.objects.create(event=event, image=f)
        process_event_photo.apply_async((photo.pk,), countdown=2)
        saved += 1
    return JsonResponse({'uploaded': saved, 'event': event.name})


@require_http_methods(['GET'])
def agent_history(request):
    user = _token_auth(request) or (request.user if request.user.is_authenticated else None)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    event_docs = mongo_store.get_events_by_user(user.pk)
    event_ids = [d['id'] for d in event_docs]
    event_name_map = {d['id']: d['name'] for d in event_docs}
    event_slug_map = {d['id']: d['slug'] for d in event_docs}
    photo_docs = mongo_store.get_photos_for_events(event_ids)
    data = [{
        'id': p.get('id'),
        'filename': __import__('os').path.basename(p.get('image', '')),
        'event': event_name_map.get(p.get('event_id'), ''),
        'event_slug': event_slug_map.get(p.get('event_id'), ''),
        'uploaded_at': str(p.get('uploaded_at', '')),
        'processed': p.get('processed', False),
        'face_count': p.get('face_count', 0),
    } for p in photo_docs]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_http_methods(['POST'])
def agent_toggle_sync(request, slug):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    doc = mongo_store.get_event_by_slug(slug)
    if not doc or doc.get('created_by_id') != user.pk:
        return JsonResponse({'error': 'Event not found'}, status=404)
    event = Event(doc)
    event.agent_sync_enabled = not event.agent_sync_enabled
    event.save(update_fields=['agent_sync_enabled'])
    return JsonResponse({'enabled': event.agent_sync_enabled, 'slug': slug})


@csrf_exempt
@require_http_methods(['POST'])
def agent_update_event(request, slug):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    doc = mongo_store.get_event_by_slug(slug)
    if not doc or doc.get('created_by_id') != user.pk:
        return JsonResponse({'error': 'Event not found'}, status=404)
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    event = Event(doc)
    update_fields = []
    if 'watch_folder' in data:
        event.watch_folder = str(data['watch_folder'])
        update_fields.append('watch_folder')
    if 'agent_sync_enabled' in data:
        event.agent_sync_enabled = bool(data['agent_sync_enabled'])
        update_fields.append('agent_sync_enabled')
    if update_fields:
        event.save(update_fields=update_fields)
    return JsonResponse({
        'success': True,
        'slug': slug,
        'watch_folder': event.watch_folder,
        'agent_sync_enabled': event.agent_sync_enabled,
    })


@csrf_exempt
@require_http_methods(['GET'])
def agent_stats(request):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    event_docs = mongo_store.get_events_by_user(user.pk)
    event_ids = [d['id'] for d in event_docs]
    total_photos = sum(mongo_store.count_photos(eid) for eid in event_ids)
    processed_photos = sum(mongo_store.count_processed_photos(eid) for eid in event_ids)
    total_searches = mongo_store.count_guests_for_events(event_ids)
    return JsonResponse({
        'total_events': len(event_ids),
        'total_photos': total_photos,
        'processed_photos': processed_photos,
        'total_searches': total_searches,
    })
