import gzip
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from search.models import Movie


SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "movie_snapshot.json.gz"
MOVIE_FIELDS = [
    "title",
    "tagline",
    "synopsis",
    "genre",
    "cast",
    "director",
    "release_year",
    "language",
    "poster_url",
    "tmdb_id",
]


class Command(BaseCommand):
    help = "Load the checked-in movie catalog snapshot into the current database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=str(SNAPSHOT_PATH),
            help="Path to a gzipped JSON movie snapshot.",
        )

    def handle(self, *args, **options):
        snapshot_path = Path(options["path"])
        if not snapshot_path.exists():
            raise CommandError(f"Movie snapshot not found: {snapshot_path}")

        with gzip.open(snapshot_path, "rt", encoding="utf-8") as fh:
            movies = json.load(fh)

        created = 0
        updated = 0
        skipped = 0

        for item in movies:
            defaults = {
                field: item.get(field) or ""
                for field in MOVIE_FIELDS
                if field not in {"title", "tmdb_id", "release_year"}
            }
            defaults["release_year"] = item.get("release_year")
            defaults["embedding"] = ""

            title = (item.get("title") or "").strip()
            tmdb_id = item.get("tmdb_id")
            if not title:
                skipped += 1
                continue

            lookup = {"tmdb_id": tmdb_id} if tmdb_id else {
                "title": title,
                "release_year": item.get("release_year"),
            }
            defaults["title"] = title
            if tmdb_id:
                defaults["tmdb_id"] = tmdb_id

            _, was_created = Movie.objects.update_or_create(
                **lookup,
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Movie snapshot loaded: "
                f"{created:,} created, {updated:,} updated, {skipped:,} skipped. "
                f"Total movies: {Movie.objects.count():,}."
            )
        )
