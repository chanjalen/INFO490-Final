import json
import logging
import re
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST

from .models import Movie, SearchRecord, SearchHistory
from accounts.models import WatchlistItem
from .ai import explain_match_local, get_recommendations, search, tokenize, build_movie_text
from .gemini import (
    get_catalog_recommendations,
    get_taste_profile_recommendations,
    get_watchlist_recommendations,
    search_with_gemini,
)
from .services import (
    get_filter_options,
    get_search_categories,
    get_search_history,
    record_search,
    build_recommendations,
    SEARCH_HISTORY_SESSION_KEY, _tokenize_history,
)

logger = logging.getLogger(__name__)


def _watchlist_ids(request):
    """Return a set of movie PKs in the current user's watchlist, or empty set."""
    if request.user.is_authenticated:
        return set(
            WatchlistItem.objects.filter(user=request.user)
            .values_list("movie_id", flat=True)
        )
    return set()


def home(request):
    return render(
        request,
        "search/home.html",
        {
            "active_page": "search",
            "categories": get_search_categories(),
            "filters": get_filter_options(),
        },
    )


def results(request):
    query = request.GET.get("q", "").strip()
    genre = request.GET.get("genre", "").strip()
    language = request.GET.get("language", "").strip()
    year = request.GET.get("year", "").strip()
    focus = request.GET.get("focus", "").strip()
    groups_raw = request.GET.get("groups", "")

    query_groups = {}
    try:
        if groups_raw:
            query_groups = json.loads(groups_raw)
    except (json.JSONDecodeError, ValueError):
        pass

    flat_query = query
    group_list = query_groups.get("groups", [])
    if group_list:
        parts = []
        for grp in group_list:
            cat = grp.get("category", "")
            vals = "; ".join(grp.get("values", []))
            if vals:
                parts.append(f"{cat}: {vals}")
        if parts:
            flat_query = f"{query} | {' | '.join(parts)}".strip()

    genre = request.GET.get("genre", "").strip()
    year = request.GET.get("year", "").strip()
    language = request.GET.get("language", "").strip()

    movies_qs = Movie.objects.all()
    if genre:
        movies_qs = movies_qs.filter(genre__icontains=genre)
    if year and year.isdigit():
        movies_qs = movies_qs.filter(release_year=int(year))
    if language:
        movies_qs = movies_qs.filter(language__icontains=language)

    movie_list = list(movies_qs)
    if not movie_list:
        messages.info(
            request,
            "No movies found. Run: python manage.py fetch_tmdb_movies",
        )
        return render(request, "search/results.html", {
            "active_page":       "search",
            "categories":        get_search_categories(),
            "filters":           get_filter_options(),
            "query":             query,
            "flat_query":        flat_query,
            "movies":            [],
            "has_search":        bool(flat_query or genre or language or year),
            "selected_genre":    genre,
            "selected_language": language,
            "selected_year":     year,
            "watchlist_ids":     _watchlist_ids(request),
        })

    search_query = flat_query or " ".join(
        part for part in [genre, language, year] if part
    )
    if settings.IS_PRODUCTION:
        raw_results = search_with_gemini(search_query, movie_list, count=10)
        if not raw_results:
            logger.info(
                "Production Gemini search returned no results: use_gemini=%s model=%s query=%r catalog_size=%d",
                settings.USE_GEMINI,
                getattr(settings, "GEMINI_MODEL", ""),
                search_query,
                len(movie_list),
            )
        if not raw_results and not settings.USE_GEMINI:
            messages.warning(
                request,
                "Gemini search is not configured for production yet.",
            )
    else:
        raw_results = search(search_query, movie_list, top_k=10)
    result_count = len(raw_results)

    record_search(
        request,
        query=query,
        genre=genre,
        language=language,
        year=year,
        focus=focus,
        result_count=result_count,
    )

    if request.user.is_authenticated:
        try:
            SearchHistory.objects.create(
                user=request.user,
                query_text=flat_query,
                query_groups=query_groups,
                result_count=result_count,
            )
            SearchRecord.objects.create(
                user=request.user,
                query=query,
                focus=focus,
                genre=genre,
                language=language,
                year=year,
                result_count=result_count,
            )
        except Exception as exc:
            logger.warning("Failed to save DB history: %s", exc)

    watchlisted_ids = set()
    if request.user.is_authenticated:
        watchlisted_ids = set(
            WatchlistItem.objects.filter(user=request.user)
            .values_list("movie_id", flat=True)
        )

    q_tokens = set(tokenize(flat_query)) if flat_query.strip() else set()
    results_data = [
        {
            "movie": movie,
            "score": score,
            "score_pct": min(100, max(0, int(score * 100))),
            "in_watchlist": movie.pk in watchlisted_ids,
            "matched_keywords": sorted(q_tokens & set(tokenize(build_movie_text(movie))))[:6],
            "rank": rank,
        }
        for rank, (movie, score) in enumerate(raw_results, start=1)
    ]

    return render(
        request,
        "search/results.html",
        {
            "active_page": "search",
            "categories": get_search_categories(),
            "filters": get_filter_options(),
            "focus": focus,
            "flat_query": flat_query,
            "query": query,
            "query_groups": query_groups,
            "movies": results_data,
            "has_search": bool(flat_query or genre or language or year),
            "selected_genre": genre,
            "selected_language": language,
            "selected_year": year,
            "watchlist_ids": _watchlist_ids(request),
        },
    )

# =============================================================================
# Movie detail
# =============================================================================

def movie_detail(request, pk):
    movie = get_object_or_404(Movie, pk=pk)
    in_watchlist = (
        request.user.is_authenticated
        and WatchlistItem.objects.filter(user=request.user, movie=movie).exists()
    )

    # Related: same genre, excluding this movie, up to 6
    related_movies = []
    if movie.genre:
        primary_genre = movie.genre.split(",")[0].strip()
        related_movies = list(
            Movie.objects.filter(genre__icontains=primary_genre)
            .exclude(pk=movie.pk)
            .order_by("-release_year")[:6]
        )

    watchlist_ids = _watchlist_ids(request)

    return render(request, "search/movie_detail.html", {
        "movie":          movie,
        "in_watchlist":   in_watchlist,
        "related_movies": related_movies,
        "watchlist_ids":  watchlist_ids,
    })


# =============================================================================
# Match explanation — AJAX, fully local FLAN-T5
# =============================================================================

@login_required
def match_explain(request, pk):
    """
    AJAX: returns a locally-generated FLAN-T5 explanation of why this movie
    matches the query. Falls back to keyword-overlap template on failure.
    """
    movie = get_object_or_404(Movie, pk=pk)
    query = request.GET.get("q", "").strip()
    try:
        score = float(request.GET.get("score", "0"))
    except ValueError:
        score = 0.0

    if not query:
        return JsonResponse({"explanation": "No query provided.", "ok": False})

    explanation = explain_match_local(query, movie, score)
    return JsonResponse({"explanation": explanation, "ok": True})

def history(request):
    history_query = request.GET.get("history_q", "").strip()
    history_items = get_search_history(request, history_query)
    all_history_count = len(get_search_history(request))
    return render(
        request,
        "search/history.html",
        {
            "active_page": "history",
            "history_items": history_items,
            "history_query": history_query,
            "all_history_count": all_history_count,
        },
    )

@require_POST
def clear_history(request):
    """Clear session history and DB history (if logged in)."""
    request.session[SEARCH_HISTORY_SESSION_KEY] = []
    if request.user.is_authenticated:
        SearchHistory.objects.filter(user=request.user).delete()
    messages.success(request, "Search history cleared.")
    return redirect("history")


def _production_recommendation_profile(request, watchlist_movies: list) -> list[str]:
    """Build compact taste signals for Gemini from saved movies and searches."""
    profile_lines = []
    for movie in watchlist_movies:
        profile_lines.append(
            f"Saved movie: {movie.title} ({movie.release_year or 'N/A'}). "
            f"Genre: {movie.genre or 'Unknown'}. "
            f"Cast: {(movie.cast or '')[:140]}. "
            f"Synopsis: {(movie.synopsis or '')[:260]}"
        )

    if request.user.is_authenticated:
        histories = SearchHistory.objects.filter(user=request.user)[:10]
        for item in histories:
            if item.query_text.strip():
                profile_lines.append(f"Recent search: {item.query_text.strip()[:320]}")

    for entry in request.session.get(SEARCH_HISTORY_SESSION_KEY, [])[:10]:
        parts = []
        if entry.get("focus"):
            parts.append(f"Focus: {entry['focus']}")
        if entry.get("query"):
            parts.append(f"Query: {entry['query']}")
        if entry.get("genre"):
            parts.append(f"Genre: {entry['genre']}")
        if entry.get("language"):
            parts.append(f"Language: {entry['language']}")
        if entry.get("year"):
            parts.append(f"Year: {entry['year']}")
        if parts:
            profile_lines.append("Recent session search: " + "; ".join(parts))

    deduped = []
    seen = set()
    for line in profile_lines:
        key = line.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(line)
    return deduped[:24]


def recommended(request):
    """
    Four-tier recommendation system (highest priority first):

    Tier 0 (best): Gemini API — picks 10 movies from the catalogue that
                   best match the user's watchlist by genre, cast, and synopsis.
                   Requires: login + non-empty watchlist + GEMINI_API_KEY env var.

    Tier 1:        AI embedding-based ranking (bi-encoder taste profile).
                   Requires: login + DB search history + sentence-transformers.

    Tier 2:        Session token-counting (genre/language/keyword overlap).
                   Requires: session search history (no login needed).

    Tier 3:        Editorial defaults — most recent movies in the catalogue.
    """
    all_movies = list(Movie.objects.all().order_by("-release_year"))

    watchlisted_ids = set()
    watchlist_movies = []
    if request.user.is_authenticated:
        wl_qs = (
            WatchlistItem.objects.filter(user=request.user)
            .select_related("movie")
            .order_by("-added_at")
        )
        watchlist_movies = [item.movie for item in wl_qs[:15]]
        watchlisted_ids  = {m.pk for m in watchlist_movies}

    if settings.IS_PRODUCTION:
        rec_data = []
        if settings.USE_GEMINI:
            candidates = [m for m in all_movies if m.pk not in watchlisted_ids][:200]
            profile_lines = _production_recommendation_profile(request, watchlist_movies)
            if profile_lines:
                gemini_recs = get_taste_profile_recommendations(
                    profile_lines,
                    candidates,
                    count=24,
                )
            else:
                gemini_recs = []

            if not gemini_recs and watchlist_movies:
                gemini_recs = get_watchlist_recommendations(
                    watchlist_movies,
                    candidates[:150],
                    count=24,
                )
            if not gemini_recs:
                gemini_recs = get_catalog_recommendations(all_movies[:200], count=24)

            rec_data = [
                {
                    "movie":        movie,
                    "reason":       reason,
                    "score_pct":    None,
                    "in_watchlist": movie.pk in watchlisted_ids,
                }
                for movie, reason in gemini_recs
            ]
        elif not settings.USE_GEMINI:
            messages.warning(
                request,
                "Gemini recommendations are not configured for production yet.",
            )

        return render(request, "search/recommended.html", {
            "recommendations":  rec_data,
            "is_editorial":     False,
            "source":           "gemini",
            "watchlist_count":  len(watchlist_movies),
            "watchlist_ids":    watchlisted_ids,
        })

    # ── Tier 1: AI embedding recommendations ─────────────────────────────────
    embedded_movies = [m for m in all_movies if m.embedding]
    if request.user.is_authenticated:
        db_history = list(SearchHistory.objects.filter(user=request.user)[:10])
        if db_history:
            ai_recs = get_recommendations(
                db_history, embedded_movies, count=10, exclude_ids=watchlisted_ids
            )
            if ai_recs:
                rec_movies = [movie for movie, _ in ai_recs]
                reasons    = build_recommendations(request, rec_movies)
                rec_data   = [
                    {
                        "movie":        movie,
                        "reason":       reasons.get(
                            movie.pk,
                            f"{round(score * 100)}% match to your taste profile."
                        ),
                        "score_pct":    round(score * 100),
                        "in_watchlist": movie.pk in watchlisted_ids,
                    }
                    for movie, score in ai_recs
                ]
                return render(request, "search/recommended.html", {
                    "recommendations": rec_data,
                    "is_editorial":    False,
                    "source":          "ai",
                    "watchlist_ids":   watchlisted_ids,
                })

    # ── Tier 2: Session token-counting ───────────────────────────────────────
    raw_history = request.session.get(SEARCH_HISTORY_SESSION_KEY, [])
    if raw_history:
        genre_counts    = Counter(e["genre"].lower() for e in raw_history if e.get("genre"))
        language_counts = Counter(e["language"].lower() for e in raw_history if e.get("language"))
        query_tokens    = Counter(_tokenize_history(raw_history))

        scored = []
        for movie in all_movies:
            if movie.pk in watchlisted_ids:
                continue
            score   = 0
            reasons = []
            blob    = " ".join([
                movie.title, movie.synopsis, movie.genre, movie.cast, movie.language
            ]).lower()

            for genre, count in genre_counts.most_common():
                if genre and genre in (movie.genre or "").lower():
                    score += 4 + count
                    reasons.append(f"matches your recent interest in {movie.genre}")
                    break
            for language, count in language_counts.most_common():
                if language and language in (movie.language or "").lower():
                    score += 2 + count
                    reasons.append(f"aligns with your recent {movie.language} searches")
                    break
            token_matches = [t for t in query_tokens if t in blob]
            if token_matches:
                score += len(token_matches)
                reasons.append(f'echoes searches like "{", ".join(token_matches[:3])}"')
            if score > 0:
                scored.append((score, movie.release_year or 0, movie, reasons))

        scored.sort(key=lambda x: (-x[0], -x[1], x[2].title))
        rec_data = [
            {
                "movie":        movie,
                "reason":       reasons[0] if reasons else "Recommended from your recent activity.",
                "score_pct":    None,
                "in_watchlist": movie.pk in watchlisted_ids,
            }
            for _, _, movie, reasons in scored[:10]
        ]
        if rec_data:
            return render(request, "search/recommended.html", {
                "recommendations": rec_data,
                "is_editorial":    False,
                "source":          "session",
                "watchlist_ids":   watchlisted_ids,
            })

    # ── Tier 3: Editorial fallback ────────────────────────────────────────────
    editorial = Movie.objects.order_by("-release_year")[:10]
    rec_data  = [
        {
            "movie":        m,
            "reason":       "A strong place to start while your recommendation profile builds.",
            "score_pct":    None,
            "in_watchlist": m.pk in watchlisted_ids,
        }
        for m in editorial
    ]
    return render(request, "search/recommended.html", {
        "recommendations": rec_data,
        "is_editorial":    True,
        "source":          "editorial",
        "watchlist_ids":   watchlisted_ids,
    })


@login_required
def analytics(request):
    total = SearchRecord.objects.filter(user=request.user).count()
    return render(
        request,
        "search/analytics.html",
        {
            "active_page": "analytics",
            "total_searches": total,
        },
    )


@login_required
def analytics_data(request):
    records = SearchRecord.objects.filter(user=request.user)

    focus_counts: dict[str, int] = {}
    for rec in records.exclude(focus="").values_list("focus", flat=True):
        focus_counts[rec] = focus_counts.get(rec, 0) + 1

    _STOP = {
        "the", "a", "an", "in", "on", "at", "is", "was", "were", "are",
        "be", "to", "of", "and", "or", "with", "for", "from", "that",
        "this", "it", "he", "she", "his", "her", "they", "who", "what",
    }
    _STRUCTURE_LABELS = {
        "actor", "age", "appearance", "character", "charname", "dialogue",
        "gender", "hair", "name", "object", "place", "plot", "relationship",
        "role", "scene", "scence", "setting", "time", "twist", "visual",
    }
    tokens: list[str] = []
    for q in records.exclude(query="").values_list("query", flat=True):
        for raw_token in re.findall(r"[A-Za-z][A-Za-z'-]*:?", q):
            token = raw_token.lower().strip("'")
            is_structure_label = token.endswith(":") and token[:-1] in _STRUCTURE_LABELS
            token = token.rstrip(":")
            if (
                is_structure_label
                or len(token) <= 2
                or token in _STOP
                or token in _STRUCTURE_LABELS
            ):
                continue
            tokens.append(token)
    keyword_counts = Counter(tokens).most_common(20)

    return JsonResponse(
        {
            "categories": focus_counts,
            "keywords": [{"word": w, "count": c} for w, c in keyword_counts],
            "total": records.count(),
        }
    )


# =============================================================================
# Watchlist
# =============================================================================

@login_required
@require_POST
def toggle_watchlist(request, pk):
    movie          = get_object_or_404(Movie, pk=pk)
    entry, created = WatchlistItem.objects.get_or_create(user=request.user, movie=movie)
    if not created:
        entry.delete()
        in_watchlist = False
    else:
        in_watchlist = True
    return JsonResponse({"in_watchlist": in_watchlist, "title": movie.title})


@login_required
def watchlist_view(request):
    items = WatchlistItem.objects.filter(user=request.user).select_related("movie")
    return render(request, "accounts/watchlist.html", {"items": items})
