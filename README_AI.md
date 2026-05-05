# README_AI

## Overview

SoClose uses a fully local, three-stage retrieval pipeline for all AI features.

The system combines two fundamentally different retrieval methods, BM25 (keyword/sparse) and dense semantic search, and merges them with Reciprocal Rank Fusion before a cross-encoder re-ranker produces the final ranked results. Match explanations are generated locally by FLAN-T5.

---

## Why Hybrid Search (Not Just Semantic)?

Pure dense semantic search has a well-known weakness: **exact match failure**. If a user types "Tom Hanks island movie", the word "Tom Hanks" should be a near-certain signal — but a dense model might return films with more semantically similar synopses. Conversely, pure BM25 misses vague or descriptive queries like "melancholy film about two strangers talking all night in a European city." The hybrid approach captures both.

| Query type                                        | BM25 wins            | Dense wins            |
|---------------------------------------------------|----------------------|-----------------------|
| "Tom Hanks stranded on island"                    | ✓ (exact name match) |                       |
| "something melancholy and hopeful"                |                      | ✓ (semantic vibe)     |
| "movie with a shower scene"                       | ✓ (keyword)          | ✓ (Psycho context)    |
| "60s space odyssey HAL computer"                  | ✓ (keyword)          | ✓ (meaning)           |
| "two strangers fall in love on a train overnight" |                      | ✓ (scene description) |

---

## Model Inventory

| Model                                  | Size    | Role                                           | Stage        |
|----------------------------------------|---------|------------------------------------------------|--------------|
| `all-MiniLM-L6-v2`                     | ~22 MB  | Bi-encoder — dense retrieval + recommendations | 1b, Recs     |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~85 MB  | Cross-encoder — re-ranking                     | 2            |
| `google/flan-t5-base`                  | ~250 MB | Text generation — match explanations           | 3 (optional) |

**Total local model footprint (FLAN-T5 on): ~360 MB**
**Total local model footprint (FLAN-T5 off): ~110 MB**
**External API calls: 0**

---

## ENABLE_FLAN_T5 Toggle

FLAN-T5 is the only model that strains Render's free tier (512MB RAM). The `ENABLE_FLAN_T5` environment variable controls whether it loads:

| Environment       | `ENABLE_FLAN_T5`  | Explanation feature                        | RAM used |
|-------------------|-------------------|--------------------------------------------|----------|
| Local development | `true`            | FLAN-T5 generates 2-3 sentence explanation | ~360MB   |
| Render free tier  | `false` (default) | Keyword-overlap template (instant)         | ~110MB   |

The search pipeline: BM25, dense retrieval, RRF, cross-encoder, is completely unaffected by this toggle. Only the optional "Why this match?" panel changes behaviour.

---
## AI Workflow — Full Pipeline

```
User submits query (free text + category pills)
        │
        ▼
[views.py: results()]
  Flatten structured groups + raw text → single query string
        │
        ├─────────────────────────────────────────┐
        ▼                                         ▼
[ai_engine: bm25_search()]              [ai_engine: semantic_search()]
  BM25Okapi keyword retrieval             all-MiniLM-L6-v2 cosine similarity
  top 50 candidates                       top 50 candidates
  Excels: names, quotes, titles           Excels: vibes, scenes, mood
        │                                         │
        └──────────────┬──────────────────────────┘
                       ▼
          [ai_engine: reciprocal_rank_fusion()]
            RRF score = Σ 1/(60 + rank_i)
            Merges both lists → top 20 candidates
                       │
                       ▼
          [ai_engine: rerank()]
            cross-encoder/ms-marco-MiniLM-L-6-v2
            Scores each (query, movie_text) pair
            Returns final top 10
                       │
                       ▼
          [views.py: render results page]
            Movie cards with score bars
                       │
          User clicks "Why this match?" on a card
                       │
                       ▼
          [AJAX → views.py: match_explain()]
                       │
                       ▼
          [ai_engine: explain_match_local()]
            google/flan-t5-base text2text-generation
            ~1-2s on CPU
            Fallback: keyword-overlap template (instant)
```

### Recommendation Workflow (separate, fully local)

```
User visits /recommended/
        │
        ▼
[ai_engine: get_recommendations()]
  1. Fetch last 10 search queries from SearchHistory
  2. all-MiniLM-L6-v2 encodes all queries
  3. Average → single "taste profile" vector
  4. Cosine-rank all movies vs. taste profile
  5. Return top 6 (excluding watchlisted movies)
```

---

## Why Three Stages Instead of One?

| Approach                                      | Coverage         | Depth                  | Speed     | Cost      |
|-----------------------------------------------|------------------|------------------------|-----------|-----------|
| BM25 only                                     | Exact terms      | Shallow                | Fast      | Free      |
| Dense only                                    | Semantic meaning | Medium                 | Medium    | Free      |
| Cross-encoder only (all movies)               | Both             | Deep                   | Slow O(N) | Expensive |
| **Hybrid BM25 + Dense → RRF → Cross-encoder** | **Both**         | **Deep (top-20 only)** | **Fast**  | **Free**  |

The funnel architecture is the standard approach in production RAG systems: cheap, broad retrieval narrows the candidate pool, then the expensive re-ranker is applied only to a small pool where it's tractable.

---

## How Outputs Are Generated

- **Search results:** (movie, cross_encoder_score) pairs. Score is mapped to a 0-100 integer for UI progress bars. No LLM involved in ranking — purely numerical model outputs.

- **Match explanations:** FLAN-T5 receives an instruction prompt with the query, genre, cast, and synopsis snippet. Output is validated (length check, echo check) before returning. A keyword-overlap template is used as a deterministic fallback.

- **Recommendations:** Cosine similarity between a blended taste-profile embedding and each movie's embedding. Template string used for the reason text (no LLM needed — the score itself is the explanation).

---

## Guardrails

| Risk                           | Guardrail                                                    |
|--------------------------------|--------------------------------------------------------------|
| Empty query                    | `results()` redirects to home before any inference           |
| Malformed JSON groups          | `try/except` — falls back to raw query string                |
| No movies in DB                | Renders empty results with setup instructions                |
| No embeddings for a movie      | Skipped in dense search; still available to BM25             |
| Corrupt embedding JSON         | `try/except` around `json.loads()` — movie skipped           |
| Cross-encoder failure          | `rerank()` raises, caught in `search()`, returns RRF results |
| FLAN-T5 unavailable / failure  | `explain_match_local()` logs warning, returns template       |
| FLAN-T5 output too short       | Validated — uses template fallback                           |
| FLAN-T5 echoes the prompt      | Validated — uses template fallback                           |
| Very weak match (score < 0.15) | FLAN-T5 skipped entirely, template returned immediately      |

---

## API Comparison

### API-only version

```
Every search → embed query via OpenAI/Anthropic API → embed all movies via API → rank → API call for explanation
```

| Dimension       | API-only                                            | Our local (Option A)            |
|-----------------|-----------------------------------------------------|---------------------------------|
| **Cost**        | ~$0.05–0.20/search at scale                         | $0.00 always                    |
| **Latency**     | 400–1500ms (network)                                | ~50–100ms (local CPU)           |
| **Privacy**     | Every query sent to third party                     | Queries never leave your server |
| **Reliability** | Breaks if API is rate-limited or down               | Works offline, no dependency    |
| **Control**     | Model choice locked to provider                     | Swap any model freely           |
| **Depth**       | No cross-encoder re-ranking available via most APIs | Full re-ranking pipeline        |

### Why we chose Option A

- The dominant operation (semantic embedding) runs at zero cost at any query volume.
- BM25 requires no model at all, zero inference cost for that component.
- The cross-encoder re-ranker is the most accurate part of the pipeline and has no API equivalent.
- FLAN-T5 explanations are ~1-2s on CPU, acceptable for an on-click interaction, and free.
- The entire system works on a laptop with no internet connection.

---

## File Map

```
search/
├── ai_engine.py                           ← Full AI pipeline
│     ├── bm25_search()                    Stage 1a: keyword retrieval
│     ├── semantic_search()                Stage 1b: dense retrieval
│     ├── reciprocal_rank_fusion()         Stage 1c: RRF merge
│     ├── rerank()                         Stage 2: cross-encoder
│     ├── search()                         Full pipeline (views call this)
│     ├── explain_match_local()            Stage 3: FLAN-T5 explanation
│     └── get_recommendations()           Taste-profile recommendations
│
├── models.py                              Movie (embedding field), SearchHistory, Watchlist
├── views.py                               Django views wiring AI into user flows
├── urls.py                                URL routing incl. /explain/ AJAX endpoint
│
└── management/commands/
      ├── embed_movies.py                  Pre-compute bi-encoder embeddings
      └── load_sample_movies.py            Load 45-film curated dataset
```
