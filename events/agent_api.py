import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from events.models import Event
from photos.models import EventPhoto
from guests.models import GuestUpload


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
    events = Event.objects.filter(created_by=user).order_by('-created_at')
    data = []
    for e in events:
        searches = GuestUpload.objects.filter(event=e).count() if hasattr(GuestUpload, 'objects') else 0
        data.append({
            'id': e.id,
            'name': e.name,
            'slug': e.slug,
            'event_date': str(e.event_date),
            'description': e.description,
            'total_photos': e.total_photos,
            'processed_photos': e.processed_photos,
            'total_searches': searches,
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
    event = Event.objects.create(name=name, event_date=event_date, description=description, created_by=user)
    return JsonResponse({'id': event.id, 'slug': event.slug, 'name': event.name}, status=201)


@csrf_exempt
@require_http_methods(['POST'])
def agent_upload_photo(request, slug):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    try:
        event = Event.objects.get(slug=slug, created_by=user)
    except Event.DoesNotExist:
        return JsonResponse({'error': 'Event not found'}, status=404)
    photos_files = request.FILES.getlist('photos')
    if not photos_files:
        return JsonResponse({'error': 'No photos provided'}, status=400)
    saved = 0
    for f in photos_files:
        EventPhoto.objects.create(event=event, image=f)
        saved += 1
    return JsonResponse({'uploaded': saved, 'event': event.name})


@csrf_exempt
@require_http_methods(['GET'])
def agent_stats(request):
    user = _token_auth(request)
    if not user:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    events = Event.objects.filter(created_by=user)
    total_photos = sum(e.total_photos for e in events)
    processed_photos = sum(e.processed_photos for e in events)
    try:
        total_searches = GuestUpload.objects.filter(event__in=events).count()
    except Exception:
        total_searches = 0
    return JsonResponse({
        'total_events': events.count(),
        'total_photos': total_photos,
        'processed_photos': processed_photos,
        'total_searches': total_searches,
    })
