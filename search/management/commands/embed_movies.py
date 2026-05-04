"""
python manage.py embed_movies

Pre-computes sentence-transformer embeddings for all Movie records that don't
have one yet, and saves them to the `embedding` field as JSON.

Run this:
  • After initial data load (load_sample_movies)
  • After bulk-importing new movies
  • You do NOT need to re-run it for movies that already have embeddings.

Estimated time: ~1 second per 100 movies on CPU (no GPU needed).
"""

import json
import time

from django.core.management.base import BaseCommand

from search.ai import build_movie_text, get_bi_encoder
from search.models import Movie


class Command(BaseCommand):
    help = "Pre-compute sentence-transformer embeddings for all movies"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-embed ALL movies, even those that already have embeddings.",
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=64,
            help="Batch size for encoding (default: 64).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        batch_size = options["batch"]

        qs = Movie.objects.all() if force else Movie.objects.filter(embedding="")
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✓ All movies already have embeddings."))
            return

        self.stdout.write(f"Loading model…")
        model = get_bi_encoder()
        self.stdout.write(self.style.SUCCESS(f"Model loaded. Embedding {total} movies…"))

        movies = list(qs)
        texts = [build_movie_text(m) for m in movies]

        start = time.time()
        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        elapsed = time.time() - start

        # Bulk-update using individual saves (SQLite-safe)
        for movie, vector in zip(movies, embeddings):
            movie.embedding = json.dumps(vector.tolist())
            movie.save(update_fields=["embedding"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Done. {total} movies embedded in {elapsed:.1f}s "
                f"({total / elapsed:.0f} movies/sec)."
            )
        )
