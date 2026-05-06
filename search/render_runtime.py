import logging

from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

_PREPARED = False


def prepare_runtime_database(*, stdout=None, style_success=None, raise_errors=True):
    """
    Prepare the database for Render before traffic depends on it.

    Render has been observed starting this app through different command paths
    (Procfile, dashboard command, and plain Gunicorn). Keeping the preparation
    here lets every path run the same migration/sample-data/poster repair logic.
    """
    global _PREPARED
    if _PREPARED:
        return None

    def write(message):
        if stdout is not None:
            stdout.write(message)
        else:
            logger.info(message)

    try:
        write("Preparing Render database...")
        call_command("migrate", interactive=False, verbosity=1)
        call_command("load_sample_movies", verbosity=1)

        from search.models import Movie

        total = Movie.objects.count()
        with_posters = Movie.objects.exclude(poster_url="").count()
        table_name = Movie._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE poster_url LIKE %s",
                ["https://image.tmdb.org/t/p/w500/%"],
            )
            tmdb_posters = cursor.fetchone()[0]

        message = (
            "Render database ready: "
            f"{total} movies, {with_posters} poster URLs, "
            f"{tmdb_posters} TMDB poster URLs."
        )
        if stdout is not None and style_success is not None:
            stdout.write(style_success(message))
        else:
            write(message)
        _PREPARED = True
        return {
            "movies": total,
            "poster_urls": with_posters,
            "tmdb_poster_urls": tmdb_posters,
        }
    except Exception:
        _PREPARED = False
        logger.exception("Render database preparation failed")
        if raise_errors:
            raise
        return None
