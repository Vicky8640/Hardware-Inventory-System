# inventory/management/commands/create_initial_user.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
import os

class Command(BaseCommand):
    help = 'Creates a superuser if none exists, using environment variables for credentials.'

    def handle(self, *args, **options):
        # 1. Use secure Environment Variables for credentials
        USERNAME = os.environ.get('SUPERUSER_USERNAME', 'admin')
        EMAIL = os.environ.get('SUPERUSER_EMAIL', 'admin@example.com')
        # CRITICAL: Use a strong password fetched from an env variable.
        PASSWORD = os.environ.get('SUPERUSER_PASSWORD', None)

        if not PASSWORD:
            self.stdout.write(self.style.ERROR('FATAL: SUPERUSER_PASSWORD environment variable not set. Cannot create initial user.'))
            return
            
        if User.objects.filter(username=USERNAME).exists():
            self.stdout.write(self.style.WARNING(f'Superuser "{USERNAME}" already exists. Skipping.'))
        else:
            User.objects.create_superuser(
                username=USERNAME,
                email=EMAIL,
                password=PASSWORD
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created initial superuser: "{USERNAME}"'))