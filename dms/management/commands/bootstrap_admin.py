import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates or updates a local Django superuser for the DMS admin panel."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.getenv("DJANGO_SUPERUSER_USERNAME", "admin"))
        parser.add_argument("--password", default=os.getenv("DJANGO_SUPERUSER_PASSWORD", "admin12345"))
        parser.add_argument("--email", default=os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.local"))

    def handle(self, *args, **options):
        User = get_user_model()
        user, created = User.objects.get_or_create(username=options["username"])
        user.email = options["email"]
        user.is_staff = True
        user.is_superuser = True
        user.set_password(options["password"])
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Superuser {options['username']} {action}."))
