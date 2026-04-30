from collections import Counter
import re

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Movie, SearchRecord
from accounts.models import WatchlistItem
from .services import (
    get_filter_options,
    get_recommendations,
    get_search_categories,
    get_search_history,
    record_search,
    search_movies,
)


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

    movies = search_movies(query=query, genre=genre, language=language, year=year)
    has_search = any([query, genre, language, year])
    if has_search:
        count = movies.count()
        record_search(
            request,
            query=query,
            genre=genre,
            language=language,
            year=year,
            focus=focus,
            result_count=count,
        )
        if request.user.is_authenticated:
            SearchRecord.objects.create(
                user=request.user,
                query=query,
                focus=focus,
                genre=genre,
                language=language,
                year=year,
                result_count=count,
            )

    return render(
        request,
        "search/results.html",
        {
            "active_page": "search",
            "categories": get_search_categories(),
            "filters": get_filter_options(),
            "focus": focus,
            "query": query,
            "selected_genre": genre,
            "selected_language": language,
            "selected_year": year,
            "movies": movies,
            "has_search": has_search,
            "watchlist_ids": _watchlist_ids(request),
        },
    )


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


def recommended(request):
    recommendations, based_on_history = get_recommendations(request)
    return render(
        request,
        "search/recommended.html",
        {
            "active_page": "recommended",
            "recommendations": recommendations,
            "based_on_history": based_on_history,
            "watchlist_ids": _watchlist_ids(request),
        },
    )


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    related_movies = (
        Movie.objects.exclude(pk=movie.pk)
        .filter(genre__icontains=movie.genre)
        .order_by("-release_year", "title")[:3]
        if movie.genre
        else Movie.objects.none()
    )
    return render(
        request,
        "search/movie_detail.html",
        {
            "active_page": "search",
            "movie": movie,
            "related_movies": related_movies,
        },
    )


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

    # Category distribution
    focus_counts: dict[str, int] = {}
    for rec in records.exclude(focus="").values_list("focus", flat=True):
        focus_counts[rec] = focus_counts.get(rec, 0) + 1

    # Top keywords (stop-word filtered)
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
