"""
Refresh poster_url for every movie in the database using TMDB API.

Strategy:
  1. Movies with tmdb_id  → direct /movie/{id} lookup (fast, accurate).
  2. Movies without tmdb_id → /search/movie by title + year, accept the
     best match if its title is close enough, then update tmdb_id too.

After the run, any movie whose poster could not be sourced from TMDB will
still have the onerror letter-avatar fallback in the UI.

Usage:
  python manage.py refresh_posters
  python manage.py refresh_posters --delete-no-poster   # remove movies with no poster
  python manage.py refresh_posters --batch 500          # process at most 500 movies
"""

import time
import logging
from datetime import datetime

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from search.models import Movie

logger = logging.getLogger(__name__)

TMDB_BASE_URL   = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class RateLimiter:
    def __init__(self, max_per_second: float = 30.0):
        self.min_interval = 1.0 / max_per_second
        self._last_call   = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class TMDBClient:
    def __init__(self, api_key: str):
        self.api_key  = api_key
        self.rl       = RateLimiter()
        self.session  = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _get(self, endpoint: str, params: dict = None) -> dict | None:
        params = dict(params or {})
        params["api_key"] = self.api_key
        self.rl.wait()
        try:
            resp = self.session.get(f"{TMDB_BASE_URL}{endpoint}", params=params, timeout=10)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", 5)))
                return self._get(endpoint, params)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            logger.warning("TMDB request failed: %s", exc)
            return None

    def movie_by_id(self, tmdb_id: int) -> dict | None:
        return self._get(f"/movie/{tmdb_id}")

    def search_movie(self, title: str, year: int | None = None) -> dict | None:
        params = {"query": title, "include_adult": False}
        if year:
            params["year"] = year
        return self._get("/search/movie", params)


def _title_similarity(a: str, b: str) -> float:
    """Simple token overlap ratio — good enough for title matching."""
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(len(a_tokens), len(b_tokens))


class Command(BaseCommand):
    help = "Refresh poster_url for all movies using TMDB API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--delete-no-poster",
            action="store_true",
            help="Delete movies that have no poster after refresh",
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=0,
            help="Process at most N movies (0 = all)",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "TMDB_API_KEY", "") or ""
        if not api_key:
            raise CommandError(
                "TMDB_API_KEY is not set. Add it to your .env file."
            )

        delete_no_poster = options["delete_no_poster"]
        batch_limit      = options["batch"]

        client = TMDBClient(api_key)

        qs = Movie.objects.all().order_by("id")
        if batch_limit:
            qs = qs[:batch_limit]

        total      = qs.count()
        updated    = 0
        already_ok = 0
        not_found  = 0
        deleted    = 0
        errors     = 0

        self.stdout.write(f"Refreshing posters for {total} movies…\n")
        start = time.time()

        for i, movie in enumerate(qs.iterator(), start=1):
            poster_path = ""

            # ── Path 1: direct lookup by tmdb_id ─────────────────────────────
            if movie.tmdb_id:
                data = client.movie_by_id(movie.tmdb_id)
                if data:
                    poster_path = data.get("poster_path") or ""

            # ── Path 2: title search ──────────────────────────────────────────
            else:
                results = client.search_movie(movie.title, movie.release_year)
                if results and results.get("results"):
                    best = None
                    best_score = 0.0
                    for candidate in results["results"][:5]:
                        sim = _title_similarity(movie.title, candidate.get("title", ""))
                        if sim > best_score:
                            best_score = sim
                            best = candidate
                    if best and best_score >= 0.6:
                        poster_path = best.get("poster_path") or ""
                        if not movie.tmdb_id and best.get("id"):
                            movie.tmdb_id = best["id"]

            new_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ""

            if new_url and new_url == movie.poster_url:
                already_ok += 1
            elif new_url:
                movie.poster_url = new_url
                movie.save(update_fields=["poster_url", "tmdb_id"])
                updated += 1
            else:
                not_found += 1
                if delete_no_poster:
                    movie.delete()
                    deleted += 1

            # Progress every 100 movies
            if i % 100 == 0 or i == total:
                elapsed = time.time() - start
                rate    = i / elapsed if elapsed else 0
                self.stdout.write(
                    f"  {i:>6,}/{total:,}  "
                    f"updated {updated}  "
                    f"ok {already_ok}  "
                    f"no-poster {not_found}  "
                    f"deleted {deleted}  "
                    f"{rate:.1f}/s"
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Updated: {updated} | Already OK: {already_ok} | "
            f"No poster: {not_found} | Deleted: {deleted} | Errors: {errors}"
        ))
