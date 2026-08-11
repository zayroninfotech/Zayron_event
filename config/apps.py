from django.apps import AppConfig


class ConfigApp(AppConfig):
    name = 'config'

    def ready(self):
        from mongo_init import initialize_mongodb
        initialize_mongodb()
