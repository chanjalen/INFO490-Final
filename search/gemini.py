"""
Gemini API integration for watchlist-based movie recommendations.

Requires GEMINI_API_KEY in environment. Get a free key at:
  https://aistudio.google.com/app/apikey

Uses gemini-1.5-flash (free tier, 1M context window).
Falls back gracefully — returns [] on any error so views.py can
drop through to the session/editorial recommendation tiers.
"""

import json
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/gemini-1.5-flash-latest:generateContent"
)


def _api_key() -> str:
    return getattr(settings, "GEMINI_API_KEY", "") or ""


def get_watchlist_recommendations(
    watchlist_movies: list,
    candidate_movies: list,
    count: int = 10,
) -> list[tuple]:
    """
    Ask Gemini to select `count` movies from candidates that best match
    the user's taste as revealed by their watchlist.

    Args:
        watchlist_movies: Movie objects the user has saved (up to 15 used).
        candidate_movies: Pre-filtered pool Gemini chooses from (up to 50).
        count:            Number of recommendations to return.

    Returns:
        List of (Movie, reason_str) tuples ordered by Gemini's preference.
        Empty list when the API key is missing, watchlist is empty, or any
        error occurs — caller is responsible for the fallback.
    """
    api_key = _api_key()
    if not api_key or not watchlist_movies or not candidate_movies:
        return []

    # ── Compact watchlist summary ─────────────────────────────────────────────
    wl_lines = []
    for m in watchlist_movies[:15]:
        wl_lines.append(
            f"- {m.title} ({m.release_year or 'N/A'}): "
            f"Genre: {m.genre or 'Unknown'}. "
            f"Cast: {(m.cast or '')[:100]}. "
            f"Synopsis: {(m.synopsis or '')[:180]}"
        )

    # ── Indexed candidate list ────────────────────────────────────────────────
    cand_lines = []
    for i, m in enumerate(candidate_movies):
        cand_lines.append(
            f"[{i}] {m.title} ({m.release_year or 'N/A'}): "
            f"Genre: {m.genre or 'Unknown'}. "
            f"Cast: {(m.cast or '')[:80]}. "
            f"Synopsis: {(m.synopsis or '')[:160]}"
        )

    prompt = (
        "A movie fan loves these films:\n"
        + "\n".join(wl_lines)
        + f"\n\nFrom the candidates below, pick exactly {count} that this user "
        "would enjoy most. Base your picks on genre, cast style, tone, and "
        "thematic similarity to their watchlist. Avoid duplicates.\n\n"
        "CANDIDATES:\n"
        + "\n".join(cand_lines)
        + f"\n\nReturn ONLY a JSON array of exactly {count} objects. "
        'Each object: {"index": <number from brackets>, '
        '"reason": "<1-2 sentence personalised explanation>"}\n'
        "No markdown, no extra text — just the raw JSON array."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500},
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=25,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        # Strip markdown code fences Gemini sometimes wraps around JSON
        raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
        picks = json.loads(raw)

        results = []
        seen_pks = set()
        for pick in picks:
            idx = pick.get("index")
            reason = pick.get("reason", "Recommended based on your watchlist.")
            if not isinstance(idx, int) or not (0 <= idx < len(candidate_movies)):
                continue
            movie = candidate_movies[idx]
            if movie.pk in seen_pks:
                continue
            seen_pks.add(movie.pk)
            results.append((movie, reason))
            if len(results) >= count:
                break

        logger.info("Gemini returned %d recommendations", len(results))
        return results

    except Exception as exc:
        logger.warning("Gemini recommendation failed: %s", exc)
        return []
