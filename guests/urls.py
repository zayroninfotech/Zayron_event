from django.urls import path
from . import views

urlpatterns = [
    path('<slug:slug>/upload/', views.guest_upload, name='guest_upload'),
    path('<slug:slug>/results/<int:upload_id>/', views.guest_results, name='guest_results'),
    path('<slug:slug>/download/<int:photo_id>/', views.download_photo, name='download_photo'),
    path('<slug:slug>/zip/<int:upload_id>/', views.download_zip, name='download_zip'),
    path('api/status/<int:upload_id>/', views.guest_status_api, name='guest_status_api'),
]
