from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

USERNAME = 'vamsi'
PASSWORD = 'Zayron@2026'
EMAIL = 'zayroninfotech@gmail.com'


class Command(BaseCommand):
    help = 'Create the default superadmin account (idempotent)'

    def handle(self, *args, **options):
        if User.objects.filter(username=USERNAME).exists():
            user = User.objects.get(username=USERNAME)
            user.set_password(PASSWORD)
            user.is_staff = True
            user.is_superuser = True
            user.save()
            self.stdout.write(self.style.WARNING(f'Superuser "{USERNAME}" already existed — password reset.'))
        else:
            User.objects.create_superuser(username=USERNAME, email=EMAIL, password=PASSWORD)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{USERNAME}" created successfully.'))
