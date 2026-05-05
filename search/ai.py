import json
import logging
import string
from typing import Optional

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Model Names
BI_ENCODER_MODEL = "all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
FLAN_T5_MODEL = "google/flan-t5-base"

_bi_encoder: Optional[SentenceTransformer] = None
_cross_encoder: Optional[CrossEncoder] = None
_flan_pipeline = None

_bm25_index = None
_bm25_pks = None

def get_bi_encoder() -> SentenceTransformer:
    global _bi_encoder
    if _bi_encoder is None:
        logger.info("Loading bi-encoder: %s", BI_ENCODER_MODEL)
        _bi_encoder = SentenceTransformer(BI_ENCODER_MODEL)
    return _bi_encoder


def get_cross_encoder() -> CrossEncoder:
    global _cross_encoder
    if _cross_encoder is None:
        logger.info("Loading cross-encoder: %s", CROSS_ENCODER_MODEL)
        _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL, max_length=512)
    return _cross_encoder


def get_flan_pipeline():
    """Return the cached FLAN-T5 text2text pipeline, loading on first call."""
    global _flan_pipeline
    if _flan_pipeline is None:
        logger.info("Loading FLAN-T5: %s", FLAN_T5_MODEL)
        from transformers import pipeline
        _flan_pipeline = pipeline(
            "text2text-generation",
            model=FLAN_T5_MODEL,
        )
    return _flan_pipeline

def _flan_enabled() -> bool:
    try:
        from django.conf import settings
        return getattr(settings, "FLAN_T5_ENABLED", False)
    except Exception:
        return False

# =============================================================================
# Text utilities
# =============================================================================

_STOPWORDS = {
    "a","an","the","and","or","but","in","on","at","to","for","of","with",
    "by","from","is","are","was","were","be","been","i","my","me","this",
    "that","it","its","as","so","do","did","not","no","who","what","which",
    "there","their","they","he","she","we","you","can","will","just","also",
    "about","some","into","has","have","had","its","after","before","when",
}


def tokenize(text: str) -> list[str]:
    """
    Lowercase → strip punctuation → split → drop stopwords.
    Keeps proper nouns and numbers intact (actor names, years, etc.)
    """
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t and t not in _STOPWORDS]


def build_movie_text(movie) -> str:
    """
    Concatenate all searchable movie fields into one rich string.
    Used for BM25 tokenisation, dense embedding, and explanation prompts.
    """
    parts = []
    if movie.title:
        parts.append(f"Title: {movie.title}")
    if getattr(movie, "tagline", None):
        parts.append(f"Tagline: {movie.tagline}")
    if movie.genre:
        parts.append(f"Genre: {movie.genre}")
    if movie.synopsis:
        parts.append(f"Plot: {movie.synopsis}")
    if movie.cast:
        parts.append(f"Cast: {movie.cast}")
    if getattr(movie, "director", None):
        parts.append(f"Director: {movie.director}")
    if movie.release_year:
        parts.append(f"Year: {movie.release_year}")
    return " | ".join(parts)

# =============================================================================
# Stage 1a — BM25 (sparse / keyword retrieval)
# =============================================================================

def _build_bm25_index(movies: list) -> None:
    global _bm25_index, _bm25_pks
    from rank_bm25 import BM25Okapi
    logger.info("Building BM25 index over %d movies", len(movies))
    corpus      = [tokenize(build_movie_text(m)) for m in movies]
    _bm25_index = BM25Okapi(corpus)
    _bm25_pks   = [m.pk for m in movies]


def _get_bm25_index(movies: list):
    """Return the cached BM25 index, rebuilding if the movie list has changed."""
    current_pks = [m.pk for m in movies]
    if _bm25_index is None or _bm25_pks != current_pks:
        _build_bm25_index(movies)
    return _bm25_index


def bm25_search(query: str, movies: list, top_k: int = 50) -> list[tuple]:
    """
    Keyword-based BM25 retrieval.

    Excels at: actor names, character names, movie titles, dialogue quotes,
               specific years, directors — anything where exact wording matters.

    Returns: list of (movie, bm25_score) sorted descending, zeroes excluded.
    """
    if not movies or not query.strip():
        return []
    index = _get_bm25_index(movies)
    tokens = tokenize(query)
    scores = index.get_scores(tokens)
    ranked = sorted(zip(movies, scores), key=lambda x: x[1], reverse=True)
    return [(m, float(s)) for m, s in ranked[:top_k] if s > 0.0]

# =============================================================================
# Stage 1b — Dense semantic search (bi-encoder)
# =============================================================================

def semantic_search(query: str, movies: list, top_k: int = 50) -> list[tuple]:
    """
    Dense retrieval using pre-computed sentence-transformer embeddings.

    Excels at: vague descriptions, mood/vibes, scene recollections, thematic
               queries — anything where meaning matters more than exact words.

    Returns: list of (movie, cosine_similarity) sorted descending.
    """
    if not movies or not query.strip():
        return []
    model = get_bi_encoder()
    query_vec = model.encode(query, show_progress_bar=False)
    results = []
    for movie in movies:
        if not movie.embedding:
            continue
        try:
            movie_vec = np.array(json.loads(movie.embedding), dtype=np.float32)
        except (json.JSONDecodeError, ValueError):
            continue
        score = float(
            cosine_similarity(query_vec.reshape(1, -1), movie_vec.reshape(1, -1))[0][0]
        )
        results.append((movie, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


# =============================================================================
# Stage 1c — Reciprocal Rank Fusion (RRF)
# =============================================================================

def reciprocal_rank_fusion(*ranked_lists: list[tuple], k: int = 60) -> list[tuple]:
    """
    Merge N independently ranked lists using Reciprocal Rank Fusion.

    Key property: only rank *positions* matter — the raw BM25 and cosine
    scores are discarded. This avoids any scale mismatch between the two
    retrieval systems without needing normalization.

    Returns: merged list of (movie, rrf_score) sorted descending.
    """
    rrf_scores: dict[int, float] = {}
    movie_map: dict[int, object] = {}

    for ranked_list in ranked_lists:
        for rank, (movie, _) in enumerate(ranked_list, start=1):
            pk = movie.pk
            movie_map[pk]  = movie
            rrf_scores[pk] = rrf_scores.get(pk, 0.0) + 1.0 / (k + rank)

    merged = [(movie_map[pk], rrf_scores[pk]) for pk in rrf_scores]
    merged.sort(key=lambda x: x[1], reverse=True)
    return merged


# =============================================================================
# Stage 2 — Cross-encoder re-ranking
# =============================================================================

def rerank(query: str, candidates: list[tuple], top_k: int = 10) -> list[tuple]:
    """
    Re-score candidates with a cross-encoder model.

    Unlike the bi-encoder, the cross-encoder sees the query and document
    *together* in a single forward pass, modelling fine-grained token-level
    interactions. This catches cases like:
      • "movie where someone says I'll be back" → exact dialogue match
      • "Ryan Gosling neon city night" → both actor name AND visual style

    Applied only to the top `rerank_pool` (≤ 20) candidates from RRF,
    so the cost is bounded regardless of corpus size.

    Args:
        query:      User query string.
        candidates: (movie, rrf_score) list from RRF.
        top_k:      Final results to return.

    Returns:
        List of (movie, cross_encoder_score) sorted descending.
    """
    if not candidates:
        return []
    ce = get_cross_encoder()
    pairs = [(query, build_movie_text(m)) for m, _ in candidates]
    scores = ce.predict(pairs, show_progress_bar=False).tolist()
    reranked = sorted(zip([m for m, _ in candidates], scores), key=lambda x: x[1], reverse=True)
    return reranked[:top_k]


# =============================================================================
# Full pipeline — the only function views.py needs to call for search
# =============================================================================

def search(
    query: str,
    movies: list,
    top_k: int = 10,
    rerank_pool: int = 20,
    bm25_candidates: int = 50,
    dense_candidates: int = 50,
) -> list[tuple]:
    """"
    Args:
        query:            User's free-text query (pre-flattened from query builder).
        movies:           Movie objects pre-filtered by DB-level genre/year/lang filters.
        top_k:            Final results to return.
        rerank_pool:      Candidates passed to the cross-encoder (≤ 20 recommended).
        bm25_candidates:  BM25 retrieval pool size.
        dense_candidates: Dense retrieval pool size.

    Returns:
        List of (movie, cross_encoder_score) tuples, sorted descending.
    """
    if not movies or not query.strip():
        return []

    embedded_movies = [m for m in movies if m.embedding]

    # Stage 1 — dual retrieval
    bm25_results = bm25_search(query, movies, top_k=bm25_candidates)
    dense_results = semantic_search(query, embedded_movies, top_k=dense_candidates)

    if not bm25_results and not dense_results:
        return []

    # Stage 2 — RRF fusion
    fused = reciprocal_rank_fusion(bm25_results, dense_results)
    pool  = fused[:rerank_pool]

    # Stage 3 — cross-encoder re-ranking
    return rerank(query, pool, top_k=top_k)


# =============================================================================
# Stage 3 — Local match explanation (FLAN-T5 + keyword-overlap fallback)
# =============================================================================

def _keyword_overlap(query: str, movie) -> list[str]:
    """Tokens appearing in both the query and the movie text (for the fallback)."""
    q_tokens = set(tokenize(query))
    m_tokens  = set(tokenize(build_movie_text(movie)))
    return sorted(q_tokens & m_tokens)


def explain_match_local(query: str, movie, score: float) -> str:
    """
    Generate a natural-language explanation of why a movie matches a query.

    Strategy:
      1. Try google/flan-t5-base via a text2text-generation pipeline.
         (~1-2 seconds on CPU — acceptable for an on-click interaction.)
      2. Validate the output (length, not echoing the prompt).
      3. If validation fails or FLAN-T5 is unavailable, fall back to a
         keyword-overlap template that is still genuinely informative.

    Guardrails:
      • score < 0.15  → skip inference entirely, return minimal template.
      • output < 20 chars or starts with the prompt → template fallback.
      • any exception → template fallback + warning log.

    Args:
        query: The user's search query.
        movie: Movie model instance.
        score: Cross-encoder score from the re-ranking stage.

    Returns:
        A 2-3 sentence human-readable explanation string.
    """
    overlapping = _keyword_overlap(query, movie)
    overlap_str = ", ".join(overlapping[:5]) if overlapping else "thematic elements"
    synopsis_snip = (movie.synopsis or "")[:200]

    # Template fallback — always reliable
    template = (
        f'"{movie.title}" connects to your search through {overlap_str}. '
        f"The film {synopsis_snip[:150]}{'…' if len(synopsis_snip) > 150 else ''} — "
        f"matching the mood and specifics you described."
    )

    # Skip inference for very weak matches
    if score < 0.15:
        return template

    cast_preview = (movie.cast or "")[:100]
    prompt = (
        f"Explain in 2 sentences why the movie '{movie.title}' ({movie.release_year}) "
        f"matches this search query: \"{query}\". "
        f"Movie genre: {movie.genre}. Cast: {cast_preview}. "
        f"Plot summary: {synopsis_snip}"
    )

    try:
        pipe = get_flan_pipeline()
        output = pipe(prompt, max_new_tokens=120, do_sample=False)
        generated = output[0]["generated_text"].strip()

        # Validate output isn't degenerate
        if len(generated) < 20:
            raise ValueError("Output too short")
        if generated.lower().startswith(prompt[:25].lower()):
            raise ValueError("Model echoed the prompt")

        return generated

    except Exception as exc:
        logger.warning("FLAN-T5 explanation failed (%s) — using template fallback.", exc)
        return template


# =============================================================================
# Recommendation engine — fully local, bi-encoder average
# =============================================================================

def get_recommendations(
    search_history: list,
    all_movies: list,
    count: int = 6,
    exclude_ids: set | None = None,
) -> list[tuple]:
    """
    Personalised recommendations via taste-profile embedding.

    Method:
      1. Encode the user's last 10 search queries with the bi-encoder.
      2. Average them into a single "taste profile" vector.
      3. Cosine-rank all movies against the profile.

    100% local — no API calls, no BM25 (dense is better here since we're
    matching against a *blended* query, not a specific keyword).

    Returns:
        List of (movie, cosine_score) tuples, sorted descending.
    """
    if not search_history or not all_movies:
        return []

    exclude_ids = exclude_ids or set()
    model = get_bi_encoder()

    queries = [h.query_text for h in search_history[:10] if h.query_text.strip()]
    if not queries:
        return []

    query_embeddings = model.encode(queries, show_progress_bar=False)
    taste_profile = query_embeddings.mean(axis=0)

    results = []
    for movie in all_movies:
        if movie.pk in exclude_ids or not movie.embedding:
            continue
        try:
            movie_vec = np.array(json.loads(movie.embedding), dtype=np.float32)
        except (json.JSONDecodeError, ValueError):
            continue
        score = float(
            cosine_similarity(taste_profile.reshape(1, -1), movie_vec.reshape(1, -1))[0][0]
        )
        results.append((movie, score))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:count]


# =============================================================================
# Embedding helpers (called by embed_movies management command)
# =============================================================================

def embed_text(text: str) -> list[float]:
    return get_bi_encoder().encode(text, show_progress_bar=False).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    return get_bi_encoder().encode(texts, batch_size=64, show_progress_bar=False).tolist()