from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import Movie

SEARCH_HISTORY_SESSION_KEY = "search_history_v1"
MAX_HISTORY_ITEMS = 12

SEARCH_CATEGORIES = [
    {
        "name": "Character",
        "description": "Who was in the scene? Think actor, role, age, or a striking visual trait.",
        "placeholder": "Describe the character, actor, role, or look you remember.",
    },
    {
        "name": "Scene",
        "description": "Recall the place, time of day, or atmosphere from a memorable moment.",
        "placeholder": "Describe the setting, time, weather, or mood of the scene.",
    },
    {
        "name": "Plot",
        "description": "Use themes, conflicts, endings, or one unforgettable event.",
        "placeholder": "Describe the plot, central conflict, or ending you remember.",
    },
    {
        "name": "Dialogue",
        "description": "Partial quotes, conversations, or catchphrases still help narrow things down.",
        "placeholder": "Type a quote, phrase, or fragment of dialogue.",
    },
    {
        "name": "Visual",
        "description": "Colors, symbols, objects, or camera imagery can all become clues.",
        "placeholder": "Describe a visual clue, object, color, or camera moment.",
    },
]


def get_search_categories() -> list[dict[str, str]]:
    return SEARCH_CATEGORIES


def get_filter_options() -> dict[str, list]:
    genres = [
        genre
        for genre in Movie.objects.exclude(genre="")
        .order_by("genre")
        .values_list("genre", flat=True)
        .distinct()
    ]
    languages = [
        language
        for language in Movie.objects.exclude(language="")
        .order_by("language")
        .values_list("language", flat=True)
        .distinct()
    ]
    years = [
        year
        for year in Movie.objects.exclude(release_year__isnull=True)
        .order_by("-release_year")
        .values_list("release_year", flat=True)
        .distinct()
    ]
    return {"genres": genres, "languages": languages, "years": years}


def _build_query_filter(term: str) -> Q:
    return (
        Q(title__icontains=term)
        | Q(synopsis__icontains=term)
        | Q(genre__icontains=term)
        | Q(cast__icontains=term)
        | Q(language__icontains=term)
    )


def search_movies(
    *,
    query: str = "",
    genre: str = "",
    language: str = "",
    year: str = "",
) -> QuerySet[Movie]:
    movies = Movie.objects.all()

    if query:
        tokens = [token for token in query.split() if token]
        combined_filter = None
        for token in tokens[:6]:
            token_filter = _build_query_filter(token)
            if token.isdigit():
                token_filter |= Q(release_year=int(token))
            combined_filter = (
                token_filter if combined_filter is None else combined_filter & token_filter
            )
        if combined_filter is None:
            combined_filter = _build_query_filter(query)
        movies = movies.filter(combined_filter)

    if genre:
        movies = movies.filter(genre__icontains=genre)
    if language:
        movies = movies.filter(language__icontains=language)
    if year and year.isdigit():
        movies = movies.filter(release_year=int(year))

    return movies.order_by("-release_year", "title")


def record_search(
    request,
    *,
    query: str,
    genre: str,
    language: str,
    year: str,
    focus: str,
    result_count: int,
) -> None:
    if not any([query, genre, language, year]):
        return

    history = request.session.get(SEARCH_HISTORY_SESSION_KEY, [])
    entry = {
        "query": query,
        "genre": genre,
        "language": language,
        "year": year,
        "focus": focus,
        "result_count": result_count,
        "timestamp": timezone.now().isoformat(),
    }

    history = [
        item
        for item in history
        if not (
            item.get("query") == query
            and item.get("genre") == genre
            and item.get("language") == language
            and item.get("year") == year
            and item.get("focus") == focus
        )
    ]
    history.insert(0, entry)
    request.session[SEARCH_HISTORY_SESSION_KEY] = history[:MAX_HISTORY_ITEMS]


def _format_history_entry(entry: dict) -> dict:
    dt = datetime.fromisoformat(entry["timestamp"])
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    now = timezone.localtime()
    local_dt = timezone.localtime(dt)
    delta = now - local_dt

    if delta.total_seconds() < 3600:
        relative_time = "Just now"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() // 3600)
        relative_time = f"{hours}h ago"
    elif delta.days == 1:
        relative_time = "Yesterday"
    elif delta.days < 7:
        relative_time = f"{delta.days} days ago"
    else:
        relative_time = local_dt.strftime("%b %d, %Y")

    parts = []
    if entry.get("focus"):
        parts.append(entry["focus"])
    if entry.get("query"):
        parts.append(entry["query"])
    if entry.get("genre"):
        parts.append(f"Genre: {entry['genre']}")
    if entry.get("language"):
        parts.append(f"Language: {entry['language']}")
    if entry.get("year"):
        parts.append(f"Year: {entry['year']}")

    formatted = dict(entry)
    formatted["relative_time"] = relative_time
    formatted["summary"] = " - ".join(parts) if parts else "Untitled search"
    formatted["timestamp_display"] = local_dt.strftime("%b %d, %Y %I:%M %p")
    return formatted


def get_search_history(request, history_query: str = "") -> list[dict]:
    history = request.session.get(SEARCH_HISTORY_SESSION_KEY, [])
    formatted_history = [_format_history_entry(entry) for entry in history]

    if not history_query:
        return formatted_history

    needle = history_query.lower()
    return [
        entry
        for entry in formatted_history
        if needle in entry["summary"].lower() or needle in entry["timestamp_display"].lower()
    ]


def _tokenize_history(history: Iterable[dict]) -> list[str]:
    tokens: list[str] = []
    for entry in history:
        if entry.get("query"):
            tokens.extend(token.lower() for token in entry["query"].split() if len(token) > 2)
    return tokens


def get_recommendations(request, limit: int = 4) -> tuple[list[dict], bool]:
    history = request.session.get(SEARCH_HISTORY_SESSION_KEY, [])
    if not history:
        movies = list(Movie.objects.all().order_by("-release_year", "title")[:limit])
        return [
            {
                "movie": movie,
                "reason": "A strong place to start while your recommendation profile is still empty.",
            }
            for movie in movies
        ], False

    genre_counts = Counter(
        entry["genre"].lower()
        for entry in history
        if entry.get("genre")
    )
    language_counts = Counter(
        entry["language"].lower()
        for entry in history
        if entry.get("language")
    )
    query_tokens = Counter(_tokenize_history(history))

    scored_movies = []
    for movie in Movie.objects.all():
        score = 0
        reasons = []

        movie_genre = (movie.genre or "").lower()
        movie_language = (movie.language or "").lower()
        search_blob = " ".join(
            [
                movie.title,
                movie.synopsis,
                movie.genre,
                movie.cast,
                movie.language,
            ]
        ).lower()

        for genre, count in genre_counts.items():
            if genre and genre in movie_genre:
                score += 4 + count
                reasons.append(f"matches your recent interest in {movie.genre}")
                break

        for language, count in language_counts.items():
            if language and language in movie_language:
                score += 2 + count
                reasons.append(f"aligns with your recent {movie.language} searches")
                break

        token_matches = [token for token in query_tokens if token in search_blob]
        if token_matches:
            score += len(token_matches)
            reasons.append(f"echoes clues from searches like \"{', '.join(token_matches[:3])}\"")

        if score > 0:
            scored_movies.append((score, movie.release_year or 0, movie, reasons))

    scored_movies.sort(key=lambda item: (-item[0], -item[1], item[2].title))
    recommendations = []
    for _, _, movie, reasons in scored_movies[:limit]:
        recommendations.append(
            {
                "movie": movie,
                "reason": reasons[0] if reasons else "Recommended from your recent search activity.",
            }
        )

    if recommendations:
        return recommendations, True

    fallback = list(Movie.objects.all().order_by("-release_year", "title")[:limit])
    return [
        {
            "movie": movie,
            "reason": "Suggested from the current catalog while we build a stronger preference signal.",
        }
        for movie in fallback
    ], True
