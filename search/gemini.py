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

from .ai import bm25_search, build_movie_text, tokenize

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash"


def _api_key() -> str:
    return (getattr(settings, "GEMINI_API_KEY", "") or "").strip()


def _gemini_enabled() -> bool:
    return bool(getattr(settings, "USE_GEMINI", False) and _api_key())


def _model_name() -> str:
    return GEMINI_MODEL


def _gemini_url() -> str:
    return f"{GEMINI_BASE_URL}/models/{_model_name()}:generateContent"


def _extract_json(text: str):
    raw = re.sub(r"```(?:json)?", "", text or "").strip().strip("`").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _extract_ranked_picks(text: str) -> list[dict]:
    """
    Return ranked picks from Gemini output.

    Production search intentionally asks for numeric JSON, but this parser also
    tolerates older object output and partially malformed JSON that still
    contains index/confidence fields.
    """
    try:
        parsed = _extract_json(text)
    except json.JSONDecodeError:
        parsed = None

    picks = []
    if isinstance(parsed, list):
        for item in parsed:
            if isinstance(item, int):
                picks.append({"index": item})
            elif isinstance(item, dict):
                picks.append(item)
    elif isinstance(parsed, dict):
        values = parsed.get("results") or parsed.get("movies") or parsed.get("picks")
        if isinstance(values, list):
            for item in values:
                if isinstance(item, int):
                    picks.append({"index": item})
                elif isinstance(item, dict):
                    picks.append(item)

    if picks:
        return picks

    # Last-resort recovery for truncated object JSON like:
    # [{"index": 3, "confidence": 0.91, "reason": "unterminated...
    recovered = []
    for match in re.finditer(
        r'"index"\s*:\s*(\d+)(?:[^{}[\]]{0,120}?"confidence"\s*:\s*([0-9.]+))?',
        text or "",
    ):
        pick = {"index": int(match.group(1))}
        if match.group(2):
            try:
                pick["confidence"] = float(match.group(2))
            except ValueError:
                pass
        recovered.append(pick)
    return recovered


def _post_gemini(prompt: str, *, temperature: float, max_output_tokens: int) -> str:
    resp = requests.post(
        _gemini_url(),
        params={"key": _api_key()},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        },
        timeout=30,
    )
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        logger.warning(
            "Gemini request failed for model %s with status %s: %s",
            _model_name(),
            resp.status_code,
            resp.text[:500],
        )
        raise exc
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"]


def _movie_catalog_lines(movies: list, synopsis_chars: int = 260) -> list[str]:
    lines = []
    for i, movie in enumerate(movies):
        lines.append(
            f"[{i}] {movie.title} ({movie.release_year or 'N/A'}): "
            f"Genre: {movie.genre or 'Unknown'}. "
            f"Language: {movie.language or 'Unknown'}. "
            f"Director: {getattr(movie, 'director', '') or 'Unknown'}. "
            f"Cast: {(movie.cast or '')[:120]}. "
            f"Synopsis: {(movie.synopsis or '')[:synopsis_chars]}"
        )
    return lines


def _strip_focus_labels(query: str) -> str:
    query = (query or "").strip()
    query = re.sub(
        r"\b(?:general|character|scene|plot|dialogue|visual|time of day|weather|action|name)\s*:\s*",
        " ",
        query,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", query).strip()


def _production_lexical_fallback(query: str, movies: list, count: int) -> list[tuple]:
    """
    Last-mile guardrail for production search.

    Gemini is still the first semantic ranker. If it returns no usable indexes,
    use the same lightweight lexical retrieval behavior local mode has, so vague
    searches do not collapse to an empty page.
    """
    clean_query = _strip_focus_labels(query)
    if not clean_query:
        return []

    fallback_query = " ".join([clean_query, query]).strip()
    results = bm25_search(fallback_query, movies, top_k=count)
    if not results:
        results = bm25_search(clean_query, movies, top_k=count)
    if not results:
        query_tokens = set(tokenize(clean_query))
        overlap_results = []
        for movie in movies:
            movie_tokens = set(tokenize(build_movie_text(movie)))
            overlap = query_tokens & movie_tokens
            if not overlap:
                continue
            score = len(overlap) / max(1, len(query_tokens))
            overlap_results.append((movie, score))
        results = sorted(overlap_results, key=lambda item: item[1], reverse=True)[:count]
        if not results:
            return []

    max_score = max(score for _, score in results) or 1.0
    normalised = [(movie, max(0.1, min(0.82, score / max_score * 0.82))) for movie, score in results]
    logger.info("Production lexical fallback returned %d results", len(normalised))
    return normalised


def get_watchlist_recommendations(
    watchlist_movies: list,
    candidate_movies: list,
    count: int = 24,
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
    if not _gemini_enabled():
        return []
    if not watchlist_movies or not candidate_movies:
        return []
    target_count = min(count, len(candidate_movies))

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
        + f"\n\nFrom the candidates below, pick up to {target_count} that this user "
        "would enjoy most. Base your picks on genre, cast style, tone, and "
        "thematic similarity to their watchlist. Avoid duplicates.\n\n"
        "CANDIDATES:\n"
        + "\n".join(cand_lines)
        + f"\n\nReturn ONLY a JSON array of up to {target_count} objects. "
        'Each object: {"index": <number from brackets>, '
        '"reason": "<1-2 sentence personalised explanation>"}\n'
        "No markdown, no extra text — just the raw JSON array."
    )

    try:
        raw = _post_gemini(
            prompt,
            temperature=0.4,
            max_output_tokens=2600,
        )
        picks = _extract_json(raw)

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
            if len(results) >= target_count:
                break

        logger.info("Gemini returned %d recommendations", len(results))
        return results

    except Exception as exc:
        logger.warning("Gemini recommendation failed: %s", exc)
        return []


def get_taste_profile_recommendations(
    profile_lines: list[str],
    candidate_movies: list,
    count: int = 24,
) -> list[tuple]:
    """
    Ask Gemini to recommend movies from searches and/or saved movies.

    Candidate evidence includes genre, cast, director, language, and synopsis.
    """
    profile_lines = [line.strip() for line in profile_lines if line and line.strip()]
    if not _gemini_enabled() or not profile_lines or not candidate_movies:
        return []

    target_count = min(count, len(candidate_movies))
    prompt = (
        "You are a movie recommendation engine. Infer the user's taste from "
        "their recent searches and saved movies. Recommend movies by comparing "
        "genre, cast, synopsis, tone, plot themes, director, and language. Do "
        "not require exact keyword overlap. Only choose from numbered candidate "
        "entries.\n\n"
        "USER TASTE PROFILE:\n"
        + "\n".join(f"- {line[:360]}" for line in profile_lines[:24])
        + "\n\nCANDIDATES:\n"
        + "\n".join(_movie_catalog_lines(candidate_movies, synopsis_chars=280))
        + f"\n\nReturn ONLY a JSON array of up to {target_count} objects. "
        'Each object must be: {"index": <number>, '
        '"reason": "<1-2 sentence explanation referencing genre, cast, synopsis, tone, or theme>"}. '
        "No markdown, no prose outside JSON."
    )

    try:
        picks = _extract_json(
            _post_gemini(prompt, temperature=0.35, max_output_tokens=3000)
        )
        results = []
        seen_pks = set()
        for pick in picks:
            idx = pick.get("index")
            reason = pick.get(
                "reason",
                "Recommended from your recent searches and saved movies.",
            )
            if not isinstance(idx, int) or not (0 <= idx < len(candidate_movies)):
                continue
            movie = candidate_movies[idx]
            if movie.pk in seen_pks:
                continue
            seen_pks.add(movie.pk)
            results.append((movie, reason))
            if len(results) >= target_count:
                break

        logger.info("Gemini returned %d taste-profile recommendations", len(results))
        return results
    except Exception as exc:
        logger.warning("Gemini taste-profile recommendation failed: %s", exc)
        return []


def get_catalog_recommendations(
    candidate_movies: list,
    count: int = 24,
) -> list[tuple]:
    """
    Ask Gemini to curate a broad recommendation shelf from the catalog.

    This powers production recommendations for logged-out users and users who
    have not built a watchlist yet, while keeping Render fully Gemini-only.
    """
    if not _gemini_enabled() or not candidate_movies:
        return []

    target_count = min(count, len(candidate_movies))
    prompt = (
        "You are curating the recommendation tab for a movie finder app. Pick a "
        "large, diverse shelf from the catalog below. Balance crowd-pleasers, "
        "critically liked titles, different genres, languages, eras, moods, and "
        "hidden gems. Choose movies that are likely to help a new user discover "
        "the catalog quickly. Only choose from numbered catalog entries.\n\n"
        "CATALOG:\n"
        + "\n".join(_movie_catalog_lines(candidate_movies, synopsis_chars=220))
        + f"\n\nReturn ONLY a JSON array of up to {target_count} objects. "
        'Each object must be: {"index": <number>, '
        '"reason": "<1 sentence discovery reason>"}. '
        "No markdown, no prose outside JSON."
    )

    try:
        picks = _extract_json(
            _post_gemini(prompt, temperature=0.35, max_output_tokens=3000)
        )
        results = []
        seen_pks = set()
        for pick in picks:
            idx = pick.get("index")
            reason = pick.get("reason", "A strong discovery pick from the current catalog.")
            if not isinstance(idx, int) or not (0 <= idx < len(candidate_movies)):
                continue
            movie = candidate_movies[idx]
            if movie.pk in seen_pks:
                continue
            seen_pks.add(movie.pk)
            results.append((movie, reason))
            if len(results) >= target_count:
                break

        logger.info("Gemini returned %d catalog recommendations", len(results))
        return results
    except Exception as exc:
        logger.warning("Gemini catalog recommendation failed: %s", exc)
        return []


def find_search_candidates(
    query: str,
    catalog_movies: list,
    count: int = 30,
    chunk_size: int = 60,
    max_catalog: int = 500,
) -> list:
    """
    Ask Gemini to select a candidate pool before local BM25 ranking.

    This keeps the Render request bounded: Gemini sees compact chunks of the
    catalog and returns indexes; BM25 then ranks the selected candidates.
    """
    api_key = _api_key()
    if not _gemini_enabled():
        return []
    query = (query or "").strip()
    if not api_key or not query or not catalog_movies:
        return []

    selected = []
    seen_pks = set()
    limited_catalog = catalog_movies[:max_catalog]
    per_chunk = max(3, min(12, count // 3 or 10))

    for start in range(0, len(limited_catalog), chunk_size):
        chunk = limited_catalog[start:start + chunk_size]
        cand_lines = []
        for i, movie in enumerate(chunk):
            cand_lines.append(
                f"[{i}] {movie.title} ({movie.release_year or 'N/A'}): "
                f"Genre: {movie.genre or 'Unknown'}. "
                f"Language: {movie.language or 'Unknown'}. "
                f"Cast: {(movie.cast or '')[:70]}. "
                f"Synopsis: {(movie.synopsis or '')[:170]}"
            )

        prompt = (
            "You are the first-pass candidate selector for a movie search engine. "
            "The user searched:\n"
            f'"{query}"\n\n'
            f"Pick up to {per_chunk} candidate movies from this chunk that could match "
            "the user's memory, vibe, plot clue, scene clue, cast clue, genre, or tone. "
            "Only choose from the numbered candidates.\n\n"
            "CANDIDATES:\n"
            + "\n".join(cand_lines)
            + "\n\nReturn ONLY a JSON array of objects like "
            '{"index": <number from brackets>}. No markdown and no extra text.'
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 500},
        }

        try:
            resp = requests.post(
                _gemini_url(),
                params={"key": api_key},
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            raw = re.sub(r"```(?:json)?", "", raw).strip().strip("`").strip()
            picks = json.loads(raw)
        except Exception as exc:
            logger.warning("Gemini candidate selection failed: %s", exc)
            return []

        for pick in picks:
            idx = pick.get("index")
            if not isinstance(idx, int) or not (0 <= idx < len(chunk)):
                continue
            movie = chunk[idx]
            if movie.pk in seen_pks:
                continue
            seen_pks.add(movie.pk)
            selected.append(movie)
            if len(selected) >= count:
                logger.info("Gemini selected %d search candidates", len(selected))
                return selected

    logger.info("Gemini selected %d search candidates", len(selected))
    return selected


def rank_search_results(
    query: str,
    catalog_movies: list,
    count: int = 10,
    max_catalog: int = 700,
) -> list[tuple]:
    """
    Production search path: Gemini semantically ranks the final movie results.

    This is intentionally Gemini-only: no BM25 or local model fallback is used.
    Vague clues are handled by asking Gemini to infer likely plot, mood, scene,
    visual, character, dialogue, and thematic matches across the catalog.
    """
    if not _gemini_enabled():
        return []
    query = (query or "").strip()
    if not query or not catalog_movies:
        return []

    candidates = catalog_movies[:max_catalog]
    prompt = (
        "You are the semantic search engine for a movie finder app. A user may "
        "describe a movie vaguely, by mood, scene memory, character detail, plot "
        "fragment, visual image, quote, actor, theme, or approximate year.\n\n"
        f'USER SEARCH: "{query}"\n\n'
        "Rank the best matching movies from the catalog below. Infer meaning "
        "rather than relying on exact keyword overlap. Prefer the movie that best "
        "matches the user's likely memory, even if the wording is indirect. Only "
        "choose from numbered catalog entries. For visual clues, infer likely "
        "movies from title, cast, genre, synopsis, and known film context.\n\n"
        "CATALOG:\n"
        + "\n".join(_movie_catalog_lines(candidates))
        + f"\n\nReturn ONLY a JSON array of up to {count} integer indexes, "
        "ordered best to worst. Example: [12, 4, 19]. "
        "Do not return objects, strings, reasons, markdown, or prose."
    )

    try:
        raw = _post_gemini(prompt, temperature=0.0, max_output_tokens=300)
        picks = _extract_ranked_picks(raw)
    except Exception as exc:
        logger.warning("Gemini semantic search failed: %s", exc)
        return []

    results = []
    seen_pks = set()
    for rank, pick in enumerate(picks):
        idx = pick.get("index")
        if not isinstance(idx, int) or not (0 <= idx < len(candidates)):
            continue
        movie = candidates[idx]
        if movie.pk in seen_pks:
            continue
        seen_pks.add(movie.pk)
        try:
            confidence = float(pick.get("confidence", 1.0 - (rank * 0.07)))
        except (TypeError, ValueError):
            confidence = 1.0 - (rank * 0.07)
        results.append((movie, min(1.0, max(0.1, confidence))))
        if len(results) >= count:
            break

    if not results:
        results = _production_lexical_fallback(query, candidates, count)

    logger.info("Gemini semantic search returned %d results", len(results))
    return results


def search_with_gemini(
    query: str,
    catalog_movies: list,
    count: int = 10,
) -> list[tuple]:
    """
    Production search path: Gemini chooses and ranks the final results.

    Returns a list of (Movie, score) tuples. The score is rank-based so the
    existing result card UI can keep showing match percentages without invoking
    local ranking models.
    """
    return rank_search_results(query, catalog_movies, count=count)
