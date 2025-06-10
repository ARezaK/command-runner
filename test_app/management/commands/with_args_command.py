from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'A test command that accepts arguments.'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='The name to print.')
        parser.add_argument('--shout', action='store_true', help='Shout the name in uppercase.')

    def handle(self, *args, **options):
        name = options['name']
        shout = options['shout']

        if shout:
            name = name.upper()

        self.stdout.write(f'Hello, {name}!')

        if not name:
            raise CommandError("Name cannot be empty.")

        self.stdout.write(self.style.SUCCESS(f'Successfully greeted {name}.')) 