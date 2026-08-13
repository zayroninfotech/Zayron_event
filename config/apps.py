from django.apps import AppConfig


class ConfigApp(AppConfig):
    name = 'config'
    # MongoDB collection init is handled by photos/apps.py PhotosConfig.ready()
