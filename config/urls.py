from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from events.agent_api import agent_login, agent_events, agent_create_event, agent_upload_photo, agent_stats, agent_history, agent_toggle_sync, agent_update_event

urlpatterns = [
    path('accounts/', include('accounts.urls')),
    path('dashboard/', include('events.urls')),
    path('event/', include('guests.urls')),
    path('photos/', include('photos.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    # Agent API
    path('api/agent/login/', agent_login, name='agent_login'),
    path('api/agent/events/', agent_events, name='agent_events'),
    path('api/agent/events/create/', agent_create_event, name='agent_create_event'),
    path('api/agent/upload/<slug:slug>/', agent_upload_photo, name='agent_upload_photo'),
    path('api/agent/stats/', agent_stats, name='agent_stats'),
    path('api/agent/history/', agent_history, name='agent_history'),
    path('api/agent/toggle-sync/<slug:slug>/', agent_toggle_sync, name='agent_toggle_sync'),
    path('api/agent/events/<slug:slug>/update/', agent_update_event, name='agent_update_event'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
