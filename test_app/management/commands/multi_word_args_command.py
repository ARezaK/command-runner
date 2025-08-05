from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'A test command that accepts arguments with multiple words.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--title',
            nargs='+',
            type=str,
            help='The title to print.'
        )
        parser.add_argument(
            '--author',
            nargs='+',
            type=str,
            help='The author to print.'
        )

    def handle(self, *args, **options):
        title = ' '.join(options['title']) if options['title'] else ''
        author = ' '.join(options['author']) if options['author'] else ''

        if not title and not author:
            raise CommandError("At least one of --title or --author must be provided.")

        if title:
            self.stdout.write(f'Title: {title}')

        if author:
            self.stdout.write(f'Author: {author}')

        self.stdout.write(self.style.SUCCESS('Successfully processed arguments.')) 