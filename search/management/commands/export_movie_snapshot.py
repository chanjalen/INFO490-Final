import gzip
import json
from pathlib import Path

from django.core.management.base import BaseCommand

from search.management.commands.load_movie_snapshot import MOVIE_FIELDS, SNAPSHOT_PATH
from search.models import Movie


class Command(BaseCommand):
    help = "Export the current Movie table to the checked-in gzipped snapshot format."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default=str(SNAPSHOT_PATH),
            help="Destination path for the gzipped JSON movie snapshot.",
        )

    def handle(self, *args, **options):
        snapshot_path = Path(options["path"])
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)

        count = 0
        with gzip.open(snapshot_path, "wt", encoding="utf-8") as fh:
            fh.write("[")
            first = True
            for movie in Movie.objects.order_by("tmdb_id", "title").iterator(chunk_size=1000):
                if not first:
                    fh.write(",")
                first = False
                item = {field: getattr(movie, field) for field in MOVIE_FIELDS}
                json.dump(item, fh, ensure_ascii=False, separators=(",", ":"))
                count += 1
            fh.write("]")

        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {count:,} movies to {snapshot_path} "
                f"({snapshot_path.stat().st_size:,} bytes)."
            )
        )
