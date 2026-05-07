import logging

from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

_PREPARED = False


def _maybe_import_tmdb_catalog(write):
    if not getattr(settings, "TMDB_IMPORT_ON_PREPARE", False):
        return
    if not getattr(settings, "TMDB_API_KEY", ""):
        write("TMDB import skipped: TMDB_API_KEY is not configured.")
        return

    from search.models import Movie

    current_count = Movie.objects.count()
    target_count = getattr(settings, "TMDB_IMPORT_TARGET", 50000)
    if current_count >= target_count:
        write(
            "TMDB import skipped: "
            f"{current_count} movies already meet target {target_count}."
        )
        return

    pages = getattr(settings, "TMDB_IMPORT_PAGES", 500)
    min_votes = getattr(settings, "TMDB_IMPORT_MIN_VOTES", 0)
    language = getattr(settings, "TMDB_IMPORT_LANGUAGE", "all")
    skip_details = getattr(settings, "TMDB_IMPORT_SKIP_DETAILS", False)

    write(
        "Importing TMDB catalog into Render database: "
        f"current={current_count}, target={target_count}, pages={pages}, "
        f"min_votes={min_votes}, language={language}, "
        f"skip_details={skip_details}."
    )
    command_options = {
        "pages": pages,
        "min_votes": min_votes,
        "language": language,
        "resume": True,
        "single_pass": False,
        "skip_details": skip_details,
        "verbosity": 1,
    }
    call_command("fetch_tmdb_movies", **command_options)


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
        call_command("load_movie_snapshot", verbosity=1)
        _maybe_import_tmdb_catalog(write)

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
