from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from search.models import Movie


class Command(BaseCommand):
    help = "Prepare Render runtime database before starting Gunicorn."

    def handle(self, *args, **options):
        self.stdout.write("Preparing Render database...")

        call_command("migrate", interactive=False, verbosity=1)
        call_command("load_sample_movies", verbosity=1)

        total = Movie.objects.count()
        with_posters = Movie.objects.exclude(poster_url="").count()
        table_name = Movie._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE poster_url LIKE %s",
                ["https://image.tmdb.org/t/p/w500/%"],
            )
            tmdb_posters = cursor.fetchone()[0]

        self.stdout.write(
            self.style.SUCCESS(
                "Render database ready: "
                f"{total} movies, {with_posters} poster URLs, "
                f"{tmdb_posters} TMDB poster URLs."
            )
        )
