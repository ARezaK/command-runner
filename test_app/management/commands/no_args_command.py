from django.core.management.base import BaseCommand
import time

class Command(BaseCommand):
    help = 'A simple test command that prints a message and waits.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting the simple test command...'))
        time.sleep(2)
        self.stdout.write('Doing some work...')
        time.sleep(3)
        self.stdout.write(self.style.SUCCESS('Test command finished successfully!')) 