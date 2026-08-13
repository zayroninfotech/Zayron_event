from django.urls import path
from . import views

urlpatterns = [
    path('<slug:slug>/upload/', views.bulk_upload, name='bulk_upload'),
    path('<slug:slug>/status/', views.photo_status, name='photo_status'),
    path('<slug:slug>/download-all/', views.download_all_photos, name='download_all_photos'),
    path('<slug:slug>/bulk-delete/', views.bulk_delete_photos, name='bulk_delete_photos'),
    path('<int:photo_id>/delete/', views.delete_photo, name='delete_photo'),
    path('<int:photo_id>/download/', views.download_photo, name='download_event_photo'),
]
