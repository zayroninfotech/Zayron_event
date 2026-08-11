from django.urls import path
from . import views

urlpatterns = [
    path('<slug:slug>/upload/', views.bulk_upload, name='bulk_upload'),
    path('<slug:slug>/status/', views.photo_status, name='photo_status'),
    path('<int:photo_id>/delete/', views.delete_photo, name='delete_photo'),
]
