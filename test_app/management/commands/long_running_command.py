from django.core.management.base import BaseCommand
import time

class Command(BaseCommand):
    help = 'A test command that runs for 60+ seconds to test long-running scenarios.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting long-running command...'))

        for i in range(12):
            time.sleep(5)
            self.stdout.write(f'Progress: {(i+1)*5} seconds elapsed... Still working!')

        self.stdout.write(self.style.SUCCESS('Long-running command completed successfully after 60 seconds!'))
