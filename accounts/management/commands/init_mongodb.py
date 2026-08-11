from django.core.management.base import BaseCommand
from mongo_init import initialize_mongodb


class Command(BaseCommand):
    help = 'Create MongoDB database and collections (runs automatically on startup too)'

    def handle(self, *args, **options):
        initialize_mongodb()
        self.stdout.write(self.style.SUCCESS('MongoDB initialization complete.'))
