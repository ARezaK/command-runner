from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = "Create a superuser with specified email, username, and password"

    def handle(self, *args, **options):
        email = os.environ.get("DJANGO_ADMIN_EMAIL", "admin@example.com")
        username = os.environ.get("DJANGO_ADMIN_USERNAME", "admin")
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "pass")

        try:
            User.objects.get(username=username)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' already exists."))
        except User.DoesNotExist:
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f"Superuser created with username '{username}' and email '{email}'"))
