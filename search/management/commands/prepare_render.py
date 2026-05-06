from django.core.management.base import BaseCommand

from search.render_runtime import prepare_runtime_database


class Command(BaseCommand):
    help = "Prepare Render runtime database before starting Gunicorn."

    def handle(self, *args, **options):
        prepare_runtime_database(
            stdout=self.stdout,
            style_success=self.style.SUCCESS,
            raise_errors=True,
        )
