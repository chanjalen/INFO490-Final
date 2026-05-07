# SoClose AI Documentation

This document explains how AI is integrated into SoClose, which models are used, and why the system is designed as a local/production hybrid instead of a simple API wrapper.

## AI Workflow

AI enters the app through two main user flows:

- Search: the user enters a vague movie memory on the home page.
- Recommendations: the user opens the recommendation page after building search history or a watchlist.

### Search Flow

1. The user submits free text and optional category chips from `/`.
2. `search.views.results()` reads the raw query, filters, focus category, and structured query groups.
3. Structured groups are flattened into one search string.
4. The backend chooses the search path based on environment:

   - Local development: use `search.ai.search()`.
   - Production: use `search.gemini.search_with_gemini()`.

5. The selected pipeline returns ranked `(Movie, score)` pairs.
6. The view converts scores into display percentages.
7. `search/results.html` renders the ranked movie cards.

### Local Search Pipeline

Local mode is designed to avoid API calls.

BM25 is always available and handles keyword matching over movie text built from title, tagline, genre, synopsis, cast, director, and year.

Local dense search is enabled by default. When the sentence-transformer models are available or can be downloaded into `cache/`, the app also uses:

- `all-MiniLM-L6-v2` for dense semantic retrieval.
- Reciprocal Rank Fusion to merge BM25 and dense results.
- `cross-encoder/ms-marco-MiniLM-L-6-v2` to rerank the top candidate pool.

If dense models are explicitly disabled or cannot load, local search falls back to normalized BM25 results instead of crashing.

### Production Search Pipeline

Production uses Gemini because Render's free tier cannot reliably host the full local model stack in memory.

The production path uses:

```text
gemini-2.5-flash
```

Gemini receives the user query and a compact movie catalog representation, then returns ranked movie indexes. The app maps those indexes back to `Movie` objects and renders the normal results page.

The Gemini parser is defensive: it accepts plain index arrays, structured JSON objects, wrapped JSON, and some malformed/truncated JSON that still contains usable indexes. If Gemini returns no usable results, the app has a lexical fallback guardrail to avoid a completely broken search experience.

## Recommendation Workflow

The recommendation page is available at:

```text
/recommended/
```

In production, Gemini compares the user's taste signals against the catalog. Taste signals can include:

- watchlisted movies
- recent searches
- session search activity
- genre
- cast
- synopsis
- tone and theme signals inferred from the catalog text

If a logged-in user has no history yet, production can request broad catalog recommendations from Gemini.

In local development, the app uses local recommendation tiers:

1. Dense taste-profile recommendations when local dense models and embeddings are available.
2. Session-based matching from recent searches.
3. Editorial fallback recommendations when there is not enough user data.

## Optional Match Explanation

The endpoint:

```text
/movie/<id>/explain/
```

can explain why a movie matches the user's query. It is protected by login.

Locally, the optional model is:

```text
google/flan-t5-base
```

If `FLAN_T5_ENABLED=False`, if the model is missing, or if generation fails, the app returns a deterministic template explanation based on keyword overlap and movie metadata.

## Model Selection

| Model or Method | Environment | Role | Why selected |
| --- | --- | --- | --- |
| BM25 via `rank-bm25` | Local and fallback logic | Keyword retrieval | Fast, cheap, exact-term matching, no API cost |
| `all-MiniLM-L6-v2` | Optional local | Semantic embeddings | Small sentence-transformer model suitable for CPU/local use |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | Optional local | Candidate reranking | More precise than embedding similarity when applied to a small candidate pool |
| `google/flan-t5-base` | Optional local | Match explanation | Open-source text generation fallback for explanation text |
| `gemini-2.5-flash` | Production | Semantic search and recommendations | Handles vague language well without hosting large local models on Render |

## Design Decisions

### Why a Hybrid System

The original goal was to use local/public models where possible because they reduce per-query cost and give more control over retrieval. However, the production deployment target is Render's free tier, which has limited memory and is not a good fit for loading the full local model stack.

The final design uses local models only in local development and Gemini in production. This keeps local experimentation cheap while making the deployed app practical.

### Why Not Fully API-Based

A fully API-based version would send every search, recommendation, embedding, reranking, and explanation request to an external provider. That design would be simpler to implement, but it would increase cost, reduce privacy, and make the app dependent on API quotas and external outages.

The current design is cheaper during local development because BM25 and cached local models do not have per-query API cost. It becomes more expensive or limited in production because Gemini requests are required for semantic search and recommendations. This is acceptable for a class project prototype, but not enough for large public traffic without paid quota, caching, and rate limiting.

### Dataset Coverage

The app can only return movies that exist in the database. The project includes:

- curated sample movie loading through `load_sample_movies`
- TMDB ingestion through `fetch_tmdb_movies`
- poster repair logic for curated sample rows

The TMDB ingestion command is designed to grow the catalog toward a much larger dataset, but the checked local database is not guaranteed to contain the full 50,000-movie Render import target. This means some searches can fail because the correct movie is simply absent from the database.

Future scaling should load a larger dataset, precompute embeddings offline, and store retrieval data in a scalable search index or vector database. A future version could also explore larger datasets such as PANDA-70M, especially for subtitle and scene-level retrieval beyond basic movie metadata.

## Guardrails and Failure Handling

| Risk | Guardrail |
| --- | --- |
| Empty query or empty catalog | Return no results safely |
| Malformed structured query JSON | Fall back to raw query text |
| Missing local dense models | Use BM25-only search |
| Missing movie embeddings | Skip dense scoring for that movie |
| Corrupt embedding JSON | Catch parsing errors and continue |
| Cross-encoder unavailable | Return candidate results without reranking |
| FLAN-T5 unavailable | Return template explanation |
| Gemini malformed JSON | Recover indexes when possible |
| Gemini empty response | Use production lexical fallback |
| Render starts through different command path | `prepare_render` also runs from WSGI fallback |

## Cost and Production Readiness

Local development can be very cheap because BM25 and cached local models do not require network calls at query time. The main costs are local CPU, memory, storage for cached model files, and time spent precomputing embeddings.

Production currently depends on Gemini for semantic search and recommendations. This avoids hosting large local models on Render, but it introduces API quotas, possible rate limits, and network dependency. At larger scale, such as 10,000 users per day, the current deployment would need:

- query result caching
- per-user and per-IP rate limiting
- paid Gemini quota or another scalable model provider
- background jobs for expensive work
- a larger movie catalog
- precomputed embeddings or a vector/search database
- structured logging for API errors, empty result rates, slow requests, and quota usage

## Key Files

| File | Purpose |
| --- | --- |
| `search/ai.py` | Local BM25, optional dense retrieval, reranking, explanations, and local recommendations |
| `search/gemini.py` | Production Gemini search and recommendation helpers |
| `search/views.py` | Connects AI pipelines to Django user flows |
| `search/models.py` | Movie, search record, and search history data |
| `search/management/commands/embed_movies.py` | Precomputes local embeddings |
| `search/management/commands/load_sample_movies.py` | Loads curated sample movies |
| `search/management/commands/fetch_tmdb_movies.py` | Imports larger TMDB catalog data |
| `search/management/commands/prepare_render.py` | Prepares Render database before startup |
