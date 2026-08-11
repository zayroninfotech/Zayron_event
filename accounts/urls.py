from django.urls import path
from django.contrib.auth import views as auth_views
from . import views


class BootstrapLoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = views.BootstrapAuthForm


urlpatterns = [
    path('login/', BootstrapLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('register/', views.register_view, name='register'),
]
