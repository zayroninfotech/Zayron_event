from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.event_create, name='event_create'),
    path('<slug:slug>/', views.event_detail, name='event_detail'),
    path('<slug:slug>/edit/', views.event_edit, name='event_edit'),
    path('<slug:slug>/delete/', views.event_delete, name='event_delete'),
]
