import json
import logging
import re
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST

from .models import Movie, SearchRecord, SearchHistory
from accounts.models import WatchlistItem
from .ai import explain_match_local, get_recommendations, search, tokenize, build_movie_text
from .gemini import narrow_search_results
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

    raw_results = search(flat_query, movie_list, top_k=30)
    gemini_movies = narrow_search_results(
        flat_query,
        [movie for movie, _ in raw_results],
        count=10,
    )
    if gemini_movies:
        local_scores = {movie.pk: score for movie, score in raw_results}
        raw_results = [
            (
                movie,
                local_scores.get(movie.pk, 0.0) or max(0.1, 1.0 - (rank * 0.05)),
            )
            for rank, movie in enumerate(gemini_movies)
        ]
    else:
        raw_results = raw_results[:10]
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
    from django.conf import settings as django_settings
    from .gemini import get_watchlist_recommendations

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

    # ── Tier 0: Gemini watchlist recommendations ──────────────────────────────
    gemini_key = getattr(django_settings, "GEMINI_API_KEY", "")
    if watchlist_movies and gemini_key:
        # Pre-filter candidates by genre overlap with watchlist so the prompt
        # stays compact and results stay relevant.
        watchlist_genres = set()
        for m in watchlist_movies:
            for g in (m.genre or "").split(","):
                g = g.strip().lower()
                if g:
                    watchlist_genres.add(g)

        scored_candidates = []
        for m in all_movies:
            if m.pk in watchlisted_ids:
                continue
            movie_genres = {g.strip().lower() for g in (m.genre or "").split(",") if g.strip()}
            overlap = len(watchlist_genres & movie_genres)
            scored_candidates.append((overlap, m))

        scored_candidates.sort(key=lambda x: -x[0])
        candidates = [m for _, m in scored_candidates[:50]]

        gemini_recs = get_watchlist_recommendations(watchlist_movies, candidates, count=10)
        if gemini_recs:
            rec_data = [
                {
                    "movie":        movie,
                    "reason":       reason,
                    "score_pct":    None,
                    "in_watchlist": movie.pk in watchlisted_ids,
                }
                for movie, reason in gemini_recs
            ]
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
