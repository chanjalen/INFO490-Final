"""
Fetches movies from The Movie Database (TMDB) API and saves them to the
local Movie model. Targets ~15,000 unique movies by running two discovery
passes with different sort orders, then deduplicating by tmdb_id.

Rate limiting:
  TMDB free tier allows 40 requests/second. This command targets 35 req/s
  to stay safely under the limit. At that rate, fetching 15,000 movies
  (plus ~15,000 detail calls) takes approximately 10–15 minutes.

After running this command, run:
  python manage.py embed_movies
to pre-compute sentence-transformer embeddings for all fetched movies.

Usage:
  python manage.py fetch_tmdb_movies                    # default: ~15,000 movies
  python manage.py fetch_tmdb_movies --pages 250        # ~10,000 movies (faster)
  python manage.py fetch_tmdb_movies --pages 100        # ~4,000 movies (quick test)
  python manage.py fetch_tmdb_movies --skip-details     # no cast/tagline (fastest)
  python manage.py fetch_tmdb_movies --min-votes 100    # more obscure films
  python manage.py fetch_tmdb_movies --resume           # skip already-fetched movies

Required environment variable:
  TMDB_API_KEY=your_key_here   (get a free key at themoviedb.org/settings/api)
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

DISCOVERY_PASSES = [
    {"sort_by": "popularity.desc",   "label": "popular"},
    {"sort_by": "vote_count.desc",   "label": "most voted"},
]


class RateLimiter:
    def __init__(self, max_per_second: float = 35.0):
        self.min_interval = 1.0 / max_per_second
        self._last_call   = 0.0

    def wait(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_call = time.time()


class TMDBClient:
    def __init__(self, api_key: str, rate_limiter: RateLimiter):
        self.api_key      = api_key
        self.rate_limiter = rate_limiter
        self.session      = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get(self, endpoint: str, params: dict = None, retries: int = 3) -> dict | None:
        params = params or {}
        params["api_key"] = self.api_key
        url = f"{TMDB_BASE_URL}{endpoint}"

        for attempt in range(retries):
            self.rate_limiter.wait()
            try:
                resp = self.session.get(url, params=params, timeout=10)

                if resp.status_code == 429:
                    # TMDB rate limit hit — back off and retry
                    retry_after = int(resp.headers.get("Retry-After", 5))
                    logger.warning("TMDB rate limit hit; waiting %ds", retry_after)
                    time.sleep(retry_after)
                    continue

                if resp.status_code == 404:
                    return None  # movie doesn't exist, skip silently

                resp.raise_for_status()
                return resp.json()

            except requests.RequestException as exc:
                if attempt < retries - 1:
                    wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    logger.warning("Request failed (%s), retrying in %ds", exc, wait)
                    time.sleep(wait)
                else:
                    logger.error("Request failed after %d retries: %s %s", retries, url, exc)
                    return None

        return None

    def discover_page(self, page: int, sort_by: str, min_votes: int, language: str) -> dict | None:
        return self.get("/discover/movie", params={
            "sort_by":                  sort_by,
            "vote_count.gte":           min_votes,
            "with_original_language":   language,
            "include_adult":            False,
            "page":                     page,
        })

    def movie_details(self, tmdb_id: int) -> dict | None:
        """Fetch full movie details + credits in a single API call."""
        return self.get(f"/movie/{tmdb_id}", params={
            "append_to_response": "credits",
        })


def parse_genres(genre_list: list) -> str:
    return ", ".join(g["name"] for g in genre_list if g.get("name"))


def parse_cast(credits: dict, max_cast: int = 8) -> str:
    cast = credits.get("cast", [])
    names = [c["name"] for c in cast[:max_cast] if c.get("name")]
    return ", ".join(names)


def parse_director(credits: dict) -> str:
    crew = credits.get("crew", [])
    directors = [c["name"] for c in crew if c.get("job") == "Director"]
    return directors[0] if directors else ""


def parse_release_year(release_date: str) -> int | None:
    if not release_date:
        return None
    try:
        return datetime.strptime(release_date[:10], "%Y-%m-%d").year
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Fetch ~15,000 movies from the TMDB API and save to the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--pages",
            type=int,
            default=375,
            help=(
                "Pages to fetch per discovery pass (max 500). "
                "Two passes run by default, so total movies ≈ pages × 20 × 1.5 (after dedup). "
                "Default 375 → ~15,000 unique movies."
            ),
        )
        parser.add_argument(
            "--min-votes",
            type=int,
            default=10,
            help="Minimum TMDB vote count. Lower = more obscure films. Default: 10.",
        )
        parser.add_argument(
            "--language",
            type=str,
            default="en",
            help=(
                "Original language filter (ISO 639-1 code). "
                "Default: 'en'. Use 'all' to disable the filter."
            ),
        )
        parser.add_argument(
            "--skip-details",
            action="store_true",
            help=(
                "Skip the per-movie detail call (no tagline or cast). "
                "Much faster but produces lower-quality embeddings."
            ),
        )
        parser.add_argument(
            "--resume",
            action="store_true",
            help=(
                "Skip movies already in the database (matched by tmdb_id). "
                "Use after an interrupted run to pick up where you left off."
            ),
        )
        parser.add_argument(
            "--single-pass",
            action="store_true",
            help="Run only the popularity pass (max ~10,000 movies). Faster.",
        )

    def handle(self, *args, **options):
        api_key = getattr(settings, "TMDB_API_KEY", None)
        if not api_key:
            raise CommandError(
                "TMDB_API_KEY is not set. Add it to your .env file.\n"
                "Get a free key at: https://www.themoviedb.org/settings/api"
            )

        pages        = min(options["pages"], 500)  # TMDB hard-cap: 500 pages per query
        min_votes    = options["min_votes"]
        language     = None if options["language"] == "all" else options["language"]
        skip_details = options["skip_details"]
        resume       = options["resume"]
        single_pass  = options["single_pass"]

        passes = DISCOVERY_PASSES[:1] if single_pass else DISCOVERY_PASSES

        self.stdout.write(
            f"\n{'─'*60}\n"
            f"  SoClose — TMDB Movie Fetcher\n"
            f"{'─'*60}\n"
            f"  Pages per pass : {pages} (~{pages * 20:,} movies/pass)\n"
            f"  Passes         : {len(passes)} ({', '.join(p['label'] for p in passes)})\n"
            f"  Target unique  : ~{int(pages * 20 * len(passes) * 0.75):,} movies\n"
            f"  Min votes      : {min_votes}\n"
            f"  Language       : {language or 'all'}\n"
            f"  Skip details   : {skip_details}\n"
            f"  Resume mode    : {resume}\n"
            f"{'─'*60}\n"
        )

        rate_limiter = RateLimiter(max_per_second=35.0)
        client       = TMDBClient(api_key, rate_limiter)

        # Pre-load existing tmdb_ids if resuming
        existing_ids: set[int] = set()
        if resume:
            existing_ids = set(
                Movie.objects.exclude(tmdb_id=None).values_list("tmdb_id", flat=True)
            )
            self.stdout.write(f"  Resume: {len(existing_ids):,} movies already in DB\n")

        # ── Discovery phase ────────────────────────────────────────────────────
        # Collect all tmdb_ids + basic data from discover endpoint
        discovered: dict[int, dict] = {}   # tmdb_id → basic movie data from discover

        for pass_config in passes:
            sort_by    = pass_config["sort_by"]
            pass_label = pass_config["label"]
            self.stdout.write(f"\n[Pass: {pass_label}]  Discovering movies...")

            for page in range(1, pages + 1):
                data = client.discover_page(
                    page=page,
                    sort_by=sort_by,
                    min_votes=min_votes,
                    language=language or "en",
                )
                if data is None:
                    self.stdout.write(f"  ✗ Page {page} failed, skipping")
                    continue

                results     = data.get("results", [])
                total_pages = data.get("total_pages", pages)

                for movie_data in results:
                    tmdb_id = movie_data.get("id")
                    if not tmdb_id:
                        continue
                    if resume and tmdb_id in existing_ids:
                        continue
                    if tmdb_id not in discovered:
                        discovered[tmdb_id] = movie_data

                # Progress indicator every 50 pages
                if page % 50 == 0 or page == pages:
                    self.stdout.write(
                        f"  Page {page}/{min(pages, total_pages)} — "
                        f"{len(discovered):,} unique movies found so far"
                    )

                # Stop if TMDB has fewer pages than requested
                if page >= total_pages:
                    self.stdout.write(f"  Reached last available page ({total_pages})")
                    break

        total_to_fetch = len(discovered)
        self.stdout.write(
            f"\n{'─'*60}\n"
            f"  Discovery complete: {total_to_fetch:,} unique movies to process\n"
            f"{'─'*60}"
        )

        if total_to_fetch == 0:
            self.stdout.write(self.style.WARNING("No new movies to fetch. Done."))
            return

        # ── Detail phase ───────────────────────────────────────────────────────
        # For each discovered movie, fetch full details + credits
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count   = 0
        start_time    = time.time()

        tmdb_ids = list(discovered.keys())

        for i, tmdb_id in enumerate(tmdb_ids, start=1):
            basic = discovered[tmdb_id]

            # ── Fetch details ──────────────────────────────────────────────────
            tagline  = ""
            cast_str = ""
            director = ""
            genre_str = parse_genres(basic.get("genre_ids_named", []))

            if not skip_details:
                details = client.movie_details(tmdb_id)
                if details is None:
                    skipped_count += 1
                    continue

                tagline   = details.get("tagline", "") or ""
                credits   = details.get("credits", {})
                cast_str  = parse_cast(credits)
                director  = parse_director(credits)
                genre_str = parse_genres(details.get("genres", []))
            else:
                # Basic genre data from discover uses genre IDs, not names
                # Without a detail call we only have IDs — skip genres too
                genre_str = ""

            # ── Build Movie record ─────────────────────────────────────────────
            synopsis     = basic.get("overview", "") or ""
            release_year = parse_release_year(basic.get("release_date", ""))
            poster_path  = basic.get("poster_path", "")
            poster_url   = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ""
            title        = basic.get("title", "") or basic.get("original_title", "")
            language_val = basic.get("original_language", "en")

            if not title or not synopsis:
                skipped_count += 1
                continue

            movie_defaults = {
                "title":        title,
                "tagline":      tagline,
                "synopsis":     synopsis,
                "genre":        genre_str,
                "cast":         cast_str,
                "director":     director,
                "release_year": release_year,
                "language":     language_val,
                "poster_url":   poster_url,
                # Clear embedding so embed_movies re-processes this movie
                "embedding":    "",
            }

            try:
                _, created = Movie.objects.update_or_create(
                    tmdb_id=tmdb_id,
                    defaults=movie_defaults,
                )
                if created:
                    created_count += 1
                else:
                    updated_count += 1
            except Exception as exc:
                logger.error("Failed to save tmdb_id=%s: %s", tmdb_id, exc)
                error_count += 1

            # ── Progress report every 500 movies ──────────────────────────────
            if i % 500 == 0 or i == total_to_fetch:
                elapsed  = time.time() - start_time
                rate     = i / elapsed if elapsed > 0 else 0
                eta_secs = (total_to_fetch - i) / rate if rate > 0 else 0
                eta_min  = eta_secs / 60

                self.stdout.write(
                    f"  {i:>6,}/{total_to_fetch:,}  "
                    f"✓ {created_count:,} new  "
                    f"↺ {updated_count:,} updated  "
                    f"✗ {error_count} errors  "
                    f"⏱ {rate:.0f}/s  ETA {eta_min:.1f}m"
                )

        # ── Summary ────────────────────────────────────────────────────────────
        total_elapsed = (time.time() - start_time) / 60
        total_in_db   = Movie.objects.count()

        self.stdout.write(
            f"\n{'─'*60}\n"
            f"  Fetch complete in {total_elapsed:.1f} minutes\n"
            f"  Created : {created_count:,}\n"
            f"  Updated : {updated_count:,}\n"
            f"  Skipped : {skipped_count:,}\n"
            f"  Errors  : {error_count}\n"
            f"  Total movies in DB : {total_in_db:,}\n"
            f"{'─'*60}\n"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Done. Next step:\n"
                f"  python manage.py embed_movies\n"
                f"  (~{total_in_db // 100} minutes on CPU for {total_in_db:,} movies)"
            )
        )
