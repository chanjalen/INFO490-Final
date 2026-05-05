import json
import logging
import math
import string
import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Heavy ML libraries — not installed on Render free tier.
# When absent the search pipeline falls back to BM25-only.
DENSE_LIBS_AVAILABLE = all(
    importlib.util.find_spec(name) is not None
    for name in ("numpy", "sentence_transformers", "sklearn")
) and "test" not in sys.argv

# Model names (only used when DENSE_AVAILABLE)
BI_ENCODER_MODEL    = "all-MiniLM-L6-v2"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
FLAN_T5_MODEL       = "google/flan-t5-base"

_bi_encoder    = None
_cross_encoder = None
_flan_pipeline = None
_bm25_index    = None
_bm25_pks      = None


def _dense_enabled() -> bool:
    if not DENSE_LIBS_AVAILABLE:
        return False
    try:
        from django.conf import settings
        return bool(getattr(settings, "LOCAL_DENSE_ENABLED", False))
    except Exception:
        return os.environ.get("LOCAL_DENSE_ENABLED", "False") == "True"


def _model_cache_dir(*parts: str) -> str | None:
    try:
        from django.conf import settings
        root = getattr(settings, "LOCAL_MODEL_CACHE_DIR", None)
    except Exception:
        root = None
    if not root:
        return None
    path = Path(root, *parts)
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_bi_encoder():
    if not _dense_enabled():
        return None
    global _bi_encoder
    if _bi_encoder is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading bi-encoder: %s", BI_ENCODER_MODEL)
        try:
            _bi_encoder = SentenceTransformer(
                BI_ENCODER_MODEL,
                cache_folder=_model_cache_dir("sentence-transformers"),
                local_files_only=True,
            )
        except TypeError:
            _bi_encoder = SentenceTransformer(
                BI_ENCODER_MODEL,
                cache_folder=_model_cache_dir("sentence-transformers"),
            )
        except Exception as exc:
            logger.warning("Bi-encoder cache load failed: %s", exc)
            return None
    return _bi_encoder


def get_cross_encoder():
    if not _dense_enabled():
        return None
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        logger.info("Loading cross-encoder: %s", CROSS_ENCODER_MODEL)
        try:
            _cross_encoder = CrossEncoder(
                CROSS_ENCODER_MODEL,
                max_length=512,
                local_files_only=True,
            )
        except TypeError:
            _cross_encoder = CrossEncoder(CROSS_ENCODER_MODEL, max_length=512)
        except Exception as exc:
            logger.warning("Cross-encoder cache load failed: %s", exc)
            return None
    return _cross_encoder


def get_flan_pipeline():
    global _flan_pipeline
    if _flan_pipeline is None:
        logger.info("Loading FLAN-T5: %s", FLAN_T5_MODEL)
        from transformers import pipeline
        try:
            _flan_pipeline = pipeline(
                "text2text-generation",
                model=FLAN_T5_MODEL,
                model_kwargs={
                    "cache_dir": _model_cache_dir("huggingface"),
                    "local_files_only": True,
                },
            )
        except Exception as exc:
            logger.warning("FLAN-T5 cache load failed: %s", exc)
            raise
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
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t and t not in _STOPWORDS]


def build_movie_text(movie) -> str:
    parts = []
    if movie.title:       parts.append(f"Title: {movie.title}")
    if getattr(movie, "tagline", None): parts.append(f"Tagline: {movie.tagline}")
    if movie.genre:       parts.append(f"Genre: {movie.genre}")
    if movie.synopsis:    parts.append(f"Plot: {movie.synopsis}")
    if movie.cast:        parts.append(f"Cast: {movie.cast}")
    if getattr(movie, "director", None): parts.append(f"Director: {movie.director}")
    if movie.release_year: parts.append(f"Year: {movie.release_year}")
    return " | ".join(parts)


# =============================================================================
# Stage 1a — BM25 (always available)
# =============================================================================

def _build_bm25_index(movies: list) -> None:
    global _bm25_index, _bm25_pks
    from rank_bm25 import BM25Okapi
    logger.info("Building BM25 index over %d movies", len(movies))
    corpus      = [tokenize(build_movie_text(m)) for m in movies]
    _bm25_index = BM25Okapi(corpus)
    _bm25_pks   = [m.pk for m in movies]


def _get_bm25_index(movies: list):
    current_pks = [m.pk for m in movies]
    if _bm25_index is None or _bm25_pks != current_pks:
        _build_bm25_index(movies)
    return _bm25_index


def bm25_search(query: str, movies: list, top_k: int = 50) -> list[tuple]:
    if not movies or not query.strip():
        return []
    index  = _get_bm25_index(movies)
    tokens = tokenize(query)
    semantic_tokens = [token for token in tokens if not token.isdigit()]
    scores = index.get_scores(tokens)
    ranked = sorted(zip(movies, scores), key=lambda x: x[1], reverse=True)
    results = []
    for movie, score in ranked:
        if score <= 0.0:
            continue
        if semantic_tokens:
            movie_tokens = set(tokenize(build_movie_text(movie)))
            if not (set(semantic_tokens) & movie_tokens):
                continue
        results.append((movie, float(score)))
        if len(results) >= top_k:
            break
    return results


# =============================================================================
# Stage 1b — Dense semantic search (bi-encoder) — requires DENSE_AVAILABLE
# =============================================================================

def semantic_search(query: str, movies: list, top_k: int = 50) -> list[tuple]:
    if not _dense_enabled() or not movies or not query.strip():
        return []
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    model     = get_bi_encoder()
    if model is None:
        return []
    query_vec = model.encode(query, show_progress_bar=False)
    results   = []
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
# Stage 1c — Reciprocal Rank Fusion
# =============================================================================

def reciprocal_rank_fusion(*ranked_lists: list[tuple], k: int = 60) -> list[tuple]:
    rrf_scores: dict[int, float] = {}
    movie_map:  dict[int, object] = {}
    for ranked_list in ranked_lists:
        for rank, (movie, _) in enumerate(ranked_list, start=1):
            pk = movie.pk
            movie_map[pk]  = movie
            rrf_scores[pk] = rrf_scores.get(pk, 0.0) + 1.0 / (k + rank)
    merged = [(movie_map[pk], rrf_scores[pk]) for pk in rrf_scores]
    merged.sort(key=lambda x: x[1], reverse=True)
    return merged


# =============================================================================
# Stage 2 — Cross-encoder re-ranking — requires DENSE_AVAILABLE
# =============================================================================

def rerank(query: str, candidates: list[tuple], top_k: int = 10) -> list[tuple]:
    if not _dense_enabled() or not candidates:
        return candidates[:top_k]
    ce    = get_cross_encoder()
    if ce is None:
        return candidates[:top_k]
    pairs = [(query, build_movie_text(m)) for m, _ in candidates]
    scores = ce.predict(pairs, show_progress_bar=False).tolist()
    reranked = sorted(
        zip([m for m, _ in candidates], scores),
        key=lambda x: x[1], reverse=True,
    )
    return reranked[:top_k]


def _normalize_cross_encoder(score: float) -> float:
    """Map cross-encoder logit (roughly -10..15) to [0, 1] via linear clip."""
    return min(1.0, max(0.0, (score + 10) / 25))


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
    """
    Returns list of (movie, score) where score is in [0, 1].

    BM25-only mode (DENSE_AVAILABLE=False):  scores = bm25 / max_bm25
    Full pipeline  (DENSE_AVAILABLE=True):   scores = cross-encoder mapped to [0,1]
    """
    if not movies or not query.strip():
        return []

    bm25_results = bm25_search(query, movies, top_k=bm25_candidates)

    if not _dense_enabled():
        # Lightweight mode: BM25 only, scores normalised to [0, 1]
        results = bm25_results[:top_k]
        if results:
            max_s = max(s for _, s in results) or 1.0
            results = [(m, s / max_s) for m, s in results]
        return results

    embedded_movies = [m for m in movies if m.embedding]
    dense_results   = semantic_search(query, embedded_movies, top_k=dense_candidates)

    if not bm25_results and not dense_results:
        return []

    fused = reciprocal_rank_fusion(bm25_results, dense_results)
    pool  = fused[:rerank_pool]
    reranked = rerank(query, pool, top_k=top_k)

    return [(m, _normalize_cross_encoder(s)) for m, s in reranked]


# =============================================================================
# Match explanation (FLAN-T5 + keyword-overlap fallback)
# =============================================================================

def _keyword_overlap(query: str, movie) -> list[str]:
    q_tokens = set(tokenize(query))
    m_tokens  = set(tokenize(build_movie_text(movie)))
    return sorted(q_tokens & m_tokens)


def explain_match_local(query: str, movie, score: float) -> str:
    overlapping  = _keyword_overlap(query, movie)
    overlap_str  = ", ".join(overlapping[:5]) if overlapping else "thematic elements"
    synopsis_snip = (movie.synopsis or "")[:200]

    template = (
        f'"{movie.title}" connects to your search through {overlap_str}. '
        f"The film {synopsis_snip[:150]}{'...' if len(synopsis_snip) > 150 else ''} — "
        f"matching the mood and specifics you described."
    )

    if score < 0.15 or not _flan_enabled():
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
        output    = pipe(prompt, max_new_tokens=120, do_sample=False)
        generated = output[0]["generated_text"].strip()
        if len(generated) < 20 or generated.lower().startswith(prompt[:25].lower()):
            raise ValueError("degenerate output")
        return generated
    except Exception as exc:
        logger.warning("FLAN-T5 failed (%s) — using template fallback.", exc)
        return template


# =============================================================================
# Recommendation engine
# =============================================================================

def get_recommendations(
    search_history: list,
    all_movies: list,
    count: int = 6,
    exclude_ids: set | None = None,
) -> list[tuple]:
    """
    Personalised recommendations via taste-profile embedding.
    Returns [] when DENSE_AVAILABLE is False — views.py falls through to
    session-based (Tier 2) or editorial (Tier 3) recommendations.
    """
    if not _dense_enabled() or not search_history or not all_movies:
        return []
    import numpy as np
    from sklearn.metrics.pairwise import cosine_similarity

    exclude_ids = exclude_ids or set()
    model   = get_bi_encoder()
    if model is None:
        return []
    queries = [h.query_text for h in search_history[:10] if h.query_text.strip()]
    if not queries:
        return []

    query_embeddings = model.encode(queries, show_progress_bar=False)
    taste_profile    = query_embeddings.mean(axis=0)

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
# Embedding helpers (called by embed_movies management command — local only)
# =============================================================================

def embed_text(text: str) -> list[float]:
    model = get_bi_encoder()
    if model is None:
        raise RuntimeError("Local dense models are disabled or missing from cache. Set LOCAL_DENSE_ENABLED=True after caching the model.")
    return model.encode(text, show_progress_bar=False).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = get_bi_encoder()
    if model is None:
        raise RuntimeError("Local dense models are disabled or missing from cache. Set LOCAL_DENSE_ENABLED=True after caching the model.")
    return model.encode(texts, batch_size=64, show_progress_bar=False).tolist()
