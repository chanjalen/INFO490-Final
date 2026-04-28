from django.shortcuts import get_object_or_404, render

from .models import Movie
from .services import (
    get_filter_options,
    get_recommendations,
    get_search_categories,
    get_search_history,
    record_search,
    search_movies,
)


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
        record_search(
            request,
            query=query,
            genre=genre,
            language=language,
            year=year,
            focus=focus,
            result_count=movies.count(),
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
