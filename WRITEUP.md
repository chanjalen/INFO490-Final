# SoClose — Project Writeup

## Part 2: Full Django System Implementation

---

### 2.1 Core System

#### Django Models with Meaningful Relationships

The project defines four models across two apps, connected through Django's ORM relationship system.

**`search/models.py`**

`Movie` is the central data model. It stores all film metadata used by both the UI and the AI pipeline:

```python
class Movie(models.Model):
    title        = models.CharField(max_length=255)
    tagline      = models.CharField(max_length=255, blank=True)
    synopsis     = models.TextField(blank=True)
    genre        = models.CharField(max_length=100, blank=True)
    cast         = models.TextField(blank=True)
    director     = models.CharField(max_length=150, blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    language     = models.CharField(max_length=50, blank=True)
    poster_url   = models.URLField(blank=True)
    tmdb_id      = models.IntegerField(null=True, blank=True, unique=True)
    embedding    = models.TextField(blank=True)   # JSON-serialised float vector
```

`SearchRecord` tracks per-search analytics for logged-in users, linked to Django's built-in `AUTH_USER_MODEL` via a `ForeignKey`:

```python
class SearchRecord(models.Model):
    user         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                     related_name="search_records")
    query        = models.CharField(max_length=500, blank=True)
    focus        = models.CharField(max_length=100, blank=True)   # search category chip
    genre        = models.CharField(max_length=100, blank=True)
    language     = models.CharField(max_length=50,  blank=True)
    year         = models.CharField(max_length=10,  blank=True)
    result_count = models.IntegerField(default=0)
    searched_at  = models.DateTimeField(auto_now_add=True)
```

`SearchHistory` stores the full structured query (with JSON groups) used by the AI recommendation pipeline:

```python
class SearchHistory(models.Model):
    user         = models.ForeignKey(User, on_delete=models.CASCADE,
                                     related_name="search_history")
    query_text   = models.TextField()
    query_groups = models.JSONField(default=dict, blank=True)
    result_count = models.IntegerField(default=0)
    created_at   = models.DateTimeField(auto_now_add=True)
```

**`accounts/models.py`**

`WatchlistItem` creates a many-to-many–style relationship between `User` and `Movie` with a `unique_together` constraint to prevent duplicates:

```python
class WatchlistItem(models.Model):
    user  = models.ForeignKey(User,  on_delete=models.CASCADE, related_name="watchlist_items")
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="watchlisted_by")

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-added_at"]
```

`UserProfile` extends Django's built-in `User` with a one-to-one relationship, created automatically via a `post_save` signal:

```python
class UserProfile(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE,
                                        related_name="profile")
    display_name = models.CharField(max_length=80, blank=True)
```

**Relationship summary:**

| Relationship | From | To | Type |
|---|---|---|---|
| `search_records` | `SearchRecord` | `User` | ForeignKey (CASCADE) |
| `search_history` | `SearchHistory` | `User` | ForeignKey (CASCADE) |
| `watchlist_items` | `WatchlistItem` | `User` | ForeignKey (CASCADE) |
| `watchlisted_by` | `WatchlistItem` | `Movie` | ForeignKey (CASCADE) |
| `profile` | `UserProfile` | `User` | OneToOneField (CASCADE) |

---

#### Views — Function-Based Views (FBV)

All views are function-based, organized across two apps.

**`search/views.py`** — eight views:

| View | URL | Description |
|---|---|---|
| `home()` | `/` | Renders search landing page with category chips and filter options |
| `results()` | `/results/` | Full AI search pipeline; saves to session + DB history |
| `movie_detail()` | `/movie/<pk>/` | Single film page with watchlist state |
| `match_explain()` | `/movie/<pk>/explain/` | AJAX: returns FLAN-T5 match explanation as JSON |
| `history()` | `/history/` | Lists session and DB search history |
| `clear_history()` | `/history/clear/` | POST: clears session and DB history |
| `recommended()` | `/recommended/` | Three-tier recommendation system (AI → session → editorial) |
| `analytics()` | `/analytics/` | Renders the analytics dashboard |
| `analytics_data()` | `/analytics/data/` | JSON API: aggregated keyword and category counts |
| `toggle_watchlist()` | `/movie/<pk>/watchlist/` | AJAX POST: add/remove from watchlist |
| `watchlist_view()` | `/watchlist/` | Lists all watchlisted films |

**`accounts/views.py`** — authentication and profile management:

| View | URL | Description |
|---|---|---|
| `login_view()` | `/login/` | Django `AuthenticationForm`-based login |
| `signup_view()` | `/signup/` | Custom `SignupForm` with validation |
| `logout_view()` | `/logout/` | POST-only logout |
| `update_display_name()` | `/profile/display-name/` | AJAX PATCH: updates profile |
| `update_email()` | `/profile/email/` | AJAX PATCH: updates user email |
| `update_password()` | `/profile/password/` | AJAX PATCH: Django `PasswordChangeForm` |
| `delete_account()` | `/profile/delete/` | AJAX POST: deletes account after confirmation |

---

#### Templates — Structure and Reuse

All templates extend a single base and use `{% include %}` for reusable partials.

**`search/templates/search/base.html`** — master layout:
- Defines `{% block title %}`, `{% block extra_head %}`, `{% block content %}` blocks
- Contains the sticky navigation bar with auth-conditional links
- Contains the profile side panel (shown only when authenticated)
- Loads the shared CSS (`app.css`) and JS (`app.js`) once

**Template hierarchy:**

```
base.html
├── home.html          {% extends "search/base.html" %}
│   └── _search_panel.html  ({% include %})
├── results.html       {% extends "search/base.html" %}
│   ├── _search_panel.html  ({% include %})
│   └── _movie_card.html    ({% include %}, one per result)
├── movie_detail.html  {% extends "search/base.html" %}
├── history.html       {% extends "search/base.html" %}
├── recommended.html   {% extends "search/base.html" %}
├── analytics.html     {% extends "search/base.html" %}
└── accounts/
    ├── login.html     {% extends "search/base.html" %}
    ├── signup.html    {% extends "search/base.html" %}
    └── watchlist.html {% extends "search/base.html" %}
```

**Key partials:**
- `_search_panel.html` — the query builder with text input, category chips, and filter dropdowns; included on both home and results so users can refine without returning to the landing page
- `_movie_card.html` — a self-contained film card with poster, metadata, synopsis, AI match badge, keyword tags, and watchlist toggle; used on results, recommended, and watchlist pages

---

#### Forms and User Input Handling

**`accounts/forms.py`** defines five custom forms:

```python
class SignupForm(forms.Form):
    username   = forms.CharField(...)
    email      = forms.EmailField(required=False)
    password1  = forms.CharField(widget=forms.PasswordInput)
    password2  = forms.CharField(widget=forms.PasswordInput)

    def clean(self):
        # Cross-field validation: passwords must match
        ...

class DisplayNameForm(forms.Form):
    display_name = forms.CharField(max_length=80, required=False)

class EmailUpdateForm(forms.Form):
    email = forms.EmailField()

class PasswordUpdateForm(forms.Form):
    old_password  = forms.CharField(widget=forms.PasswordInput)
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

class DeleteAccountForm(forms.Form):
    confirm = forms.CharField()

    def clean_confirm(self):
        # Must type the word "DELETE" exactly
        ...
```

Search input is handled via GET parameters in `results()`: `q` (free text), `groups` (JSON-encoded structured query groups), `genre`, `language`, `year`, and `focus`. The `groups` field is parsed with a `try/except` guard to handle malformed JSON without crashing.

---

### 2.2 Authentication

#### Login / Logout

Login (`/login/`) uses Django's built-in `AuthenticationForm` — it authenticates with `authenticate()` and `login()`, and redirects to `LOGIN_REDIRECT_URL = "/"` on success.

Signup (`/signup/`) uses the custom `SignupForm`. After successful validation it calls `User.objects.create_user()`, then immediately logs the user in.

Logout (`/logout/`) requires a POST request (`@require_POST`) to prevent CSRF-exploitable GET-based logout. It calls Django's `logout()` and redirects to `LOGOUT_REDIRECT_URL = "/"`.

#### Protected Routes

Eight views are decorated with `@login_required`:

```python
# search/views.py
@login_required
def analytics(request): ...

@login_required
def analytics_data(request): ...

@login_required
def match_explain(request, pk): ...

@login_required
@require_POST
def toggle_watchlist(request, pk): ...

@login_required
def watchlist_view(request): ...

# accounts/views.py
@login_required
def update_display_name(request): ...

@login_required
def update_email(request): ...

@login_required
def update_password(request): ...

@login_required
def delete_account(request): ...
```

Unauthenticated users are redirected to `/login/?next=<original-url>` (configured via `LOGIN_URL = "/login/"`).

#### Conditional Navigation

`base.html` shows entirely different navigation elements depending on authentication state:

```html
{% if user.is_authenticated %}
    <!-- Avatar button that opens the profile side panel -->
    <button class="avatar-btn" id="avatar-btn">
        {{ user.profile.get_initials }}
    </button>
{% else %}
    <!-- Public nav: Sign in + Sign up buttons -->
    <a href="{% url 'accounts:login' %}">Sign in</a>
    <a href="{% url 'accounts:signup' %}">Sign up</a>
{% endif %}
```

The profile panel (shown only when authenticated) contains links to `/watchlist/` and `/analytics/`, the display name and email edit forms, and the account delete dialog. These links and forms never appear to anonymous visitors.

---

### 2.3 Data & APIs

#### Internal JSON API Endpoints

The project exposes multiple JSON endpoints consumed by the frontend without page reloads:

**`GET /analytics/data/`** — analytics dashboard data:
```json
{
  "categories": {"Scene": 4, "Plot": 2, "Character": 1},
  "keywords": [{"word": "heist", "count": 3}, {"word": "dream", "count": 2}],
  "total": 12
}
```

**`GET /movie/<pk>/explain/?q=<query>&score=<score>`** — AI match explanation:
```json
{"explanation": "Inception connects to your search through dream...", "ok": true}
```

**`POST /movie/<pk>/watchlist/`** — watchlist toggle:
```json
{"in_watchlist": true, "title": "Inception"}
```

**`POST /profile/display-name/`**, **`/profile/email/`**, **`/profile/password/`**, **`/profile/delete/`** — profile management AJAX endpoints; all return `{"ok": true}` or `{"error": "..."}`.

#### Model-Driven URLs

URLs are constructed from model primary keys throughout the application:

```python
# search/urls.py
path("movie/<int:pk>/",          views.movie_detail,    name="movie_detail"),
path("movie/<int:pk>/explain/",  views.match_explain,   name="match_explain"),
path("movie/<int:pk>/watchlist/",views.toggle_watchlist, name="toggle_watchlist"),
```

Templates generate these URLs with `{% url %}` tags, keeping them decoupled from hardcoded strings:

```html
<!-- _movie_card.html -->
<a href="{% url 'movie_detail' movie.id %}">...</a>

<!-- results.html JS -->
data-url="{% url 'toggle_watchlist' movie.id %}"
```

#### Data Flow: Models → Views → Templates

The `results()` view illustrates the complete data flow:

1. **Model layer** — `Movie.objects.all()` filtered by genre/year/language; `WatchlistItem` queried for watchlist state
2. **AI layer** — the filtered movie list is passed to `search()`, which returns `(movie, score)` tuples
3. **View layer** — results are enriched with rank, `score_pct`, `matched_keywords`, and `in_watchlist` flag into a list of dicts
4. **Template layer** — `results.html` iterates over this list; each item's `movie`, `score_pct`, `matched_keywords`, and `rank` are passed to `_movie_card.html`

```python
# views.py
q_tokens = set(tokenize(flat_query))
results_data = [
    {
        "movie":            movie,
        "score":            score,
        "score_pct":        min(100, max(0, int((score + 10) * 5))),
        "in_watchlist":     movie.pk in watchlisted_ids,
        "matched_keywords": sorted(q_tokens & set(tokenize(build_movie_text(movie))))[:6],
        "rank":             rank,
    }
    for rank, (movie, score) in enumerate(raw_results, start=1)
]
```

```html
<!-- results.html -->
{% for item in movies %}
    {% include "search/_movie_card.html" with
       movie=item.movie
       score_pct=item.score_pct
       matched_keywords=item.matched_keywords
       rank=item.rank %}
{% endfor %}
```

---

### 2.4 Data Features

#### Analytics / Report Page

`/analytics/` is a dedicated report page (`@login_required`) that shows:
- **Total searches** — count of all `SearchRecord` rows for the current user
- **Favourite category** — the `focus` field value with the highest count
- **Top keyword** — the most frequent non-stop-word token across all queries
- **Category distribution** — donut chart
- **Top keywords** — horizontal bar chart
- **Keyword cloud** — spiral word cloud with frequency-mapped font size

The page fetches data from the `/analytics/data/` JSON API and renders all three Chart.js visualisations client-side.

#### Data Visualization

Three distinct visualisations are implemented in `analytics.html`:

1. **Donut chart** (Chart.js `doughnut`) — proportion of searches by category (Scene, Plot, Character, Dialogue, Visual)
2. **Horizontal bar chart** (Chart.js `bar`) — top 20 keywords by occurrence, sorted descending, with color interpolated from count
3. **Spiral word cloud** — custom JavaScript implementation using an Archimedean spiral placement algorithm with canvas-based text measurement, bounding-box collision detection, and golden-angle distribution to achieve an organic, non-overlapping layout. Font size (12px–44px), weight (500–700), and color (#4F5F3A → #6E8F4E → #9FBF6E) are all mapped to frequency

#### JSON Export

`/analytics/data/` returns a full JSON document that can be saved directly as a structured data export. The format is machine-readable and schema-consistent:

```json
{
  "categories": {"Scene": 7, "Plot": 3},
  "keywords": [
    {"word": "dream", "count": 5},
    {"word": "heist", "count": 3}
  ],
  "total": 18
}
```

#### Aggregation View

`analytics_data()` performs two aggregation passes over `SearchRecord`:

```python
# Category aggregation
focus_counts: dict[str, int] = {}
for rec in records.exclude(focus="").values_list("focus", flat=True):
    focus_counts[rec] = focus_counts.get(rec, 0) + 1

# Keyword aggregation with stop-word and structural-label filtering
tokens: list[str] = []
for q in records.exclude(query="").values_list("query", flat=True):
    for raw_token in re.findall(r"[A-Za-z][A-Za-z'-]*:?", q):
        token = raw_token.lower().strip("'")
        if token not in _STOP and token not in _STRUCTURE_LABELS:
            tokens.append(token)
keyword_counts = Counter(tokens).most_common(20)
```

---

### 2.5 Production-Aware Setup

#### Environment Variables

All secrets and environment-specific values are loaded from `.env` via `python-dotenv`:

```
SECRET_KEY=...        # Django secret key
DEBUG=True/False      # Controls debug mode and error pages
ALLOWED_HOSTS=...     # Comma-separated list (e.g. localhost,myapp.onrender.com)
TMDB_API_KEY=...      # Used only by the fetch_tmdb_movies management command
DATABASE_URL=...      # Optional: Render PostgreSQL URL (falls back to SQLite)
```

`settings.py` reads all values with `os.environ.get()` and provides safe defaults for local development:

```python
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key")
DEBUG      = os.environ.get("DEBUG", "True") == "True"
```

#### `.gitignore`

The `.gitignore` includes all standard exclusions:

```
.env
__pycache__/
*.pyc
db.sqlite3
venv/
staticfiles/
.vscode/
.idea/
*.log
media/
dist/
build/
```

The actual `.env` file is never committed. `.env.example` is committed as a template with placeholder values only.

#### No Secrets Committed

- `SECRET_KEY` is not hardcoded anywhere in version-controlled files
- `TMDB_API_KEY` is stored only in the local `.env` (excluded by `.gitignore`)
- `db.sqlite3` is excluded (contains no production data in this project)
- `settings.py` commits only fallback dev-only strings (`"dev-only-secret-key"`)

#### Clean Project Structure

```
INFO490-Final/
├── moviefinder/                   # Project config
│   ├── settings.py                # Env-var driven config
│   ├── urls.py                    # Root URL dispatch
│   ├── wsgi.py / asgi.py
├── search/                        # Main application
│   ├── models.py                  # Movie, SearchRecord, SearchHistory
│   ├── views.py                   # All search/analytics/watchlist views
│   ├── urls.py                    # URL patterns for search app
│   ├── ai.py                      # Full AI pipeline (self-contained)
│   ├── services.py                # Session history, filter options, recommendations
│   ├── admin.py                   # Admin registrations
│   ├── migrations/                # Database migration history
│   ├── management/commands/       # fetch_tmdb_movies, embed_movies, load_sample_movies
│   ├── static/search/             # app.css, app.js
│   └── templates/search/          # All search-app templates
├── accounts/                      # Authentication and profile
│   ├── models.py                  # UserProfile, WatchlistItem
│   ├── views.py                   # Auth + profile AJAX views
│   ├── forms.py                   # SignupForm and profile forms
│   ├── urls.py                    # Auth URL patterns
│   ├── signals.py                 # Auto-create UserProfile on User creation
│   └── templates/accounts/        # Login, signup, watchlist templates
├── .env.example                   # Environment variable template
├── .gitignore
├── requirements.txt
├── render.yaml                    # Render.com deployment config
├── Procfile                       # Gunicorn process definition
└── manage.py
```

---

---

## Part 3: AI Integration

---

### 3.1 AI Feature in the Actual User Flow

All three AI features are embedded in the live request/response cycle — none require the user to run a separate script or visit a special admin page.

| Feature | Entry point | User action that triggers it |
|---|---|---|
| Hybrid semantic search | `GET /results/` | Submitting any search query |
| Match explanation | `GET /movie/<pk>/explain/` | Clicking "Why this match?" on a result card |
| Personalised recommendations | `GET /recommended/` | Navigating to the Recommended page |

---

### 3.2 How User Input Is Processed

**Search:**

The user types a free-text query and optionally selects structured category chips (Scene, Plot, Character, Dialogue, Visual). Each chip can have multiple values. In `results()`:

```python
# 1. Parse JSON groups from the query builder
query_groups = json.loads(groups_raw)    # {"groups": [{"category": "Scene", "values": [...]}]}

# 2. Flatten structured groups + raw text into one query string
flat_query = f"{query} | {' | '.join(parts)}"

# 3. Apply database-level filters (genre, year, language) to narrow the candidate pool

# 4. Pass flat_query and filtered movie list to the AI pipeline
raw_results = search(flat_query, movie_list, top_k=10)
```

**Recommendation:**

```python
# 1. Fetch last 10 SearchHistory records for the user
db_history = SearchHistory.objects.filter(user=request.user)[:10]

# 2. Extract query strings and encode with the bi-encoder
queries = [h.query_text for h in db_history if h.query_text.strip()]
query_embeddings = model.encode(queries)

# 3. Average into a taste-profile vector
taste_profile = query_embeddings.mean(axis=0)

# 4. Cosine-rank all movies with stored embeddings against the taste profile
```

---

### 3.3 Models Used

| Model | Size | Library | Role |
|---|---|---|---|
| `all-MiniLM-L6-v2` | ~22 MB | `sentence-transformers` | Bi-encoder: encodes queries and documents into dense vectors for semantic similarity search and recommendation taste-profile construction |
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~85 MB | `sentence-transformers` | Cross-encoder: re-scores top-20 candidates by jointly encoding the query and each movie text in a single forward pass, producing the final ranking |
| `google/flan-t5-base` | ~250 MB | `transformers` | Text-to-text generation: produces natural-language explanations of why a movie matches a query (optional; controlled by `FLAN_T5_ENABLED` env var) |

All models are downloaded automatically from Hugging Face on first use and cached locally. **No external API calls are made at inference time.** Total model footprint: ~360 MB (FLAN-T5 on) / ~110 MB (FLAN-T5 off).

---

### 3.4 Full AI Pipeline

```
User query (text + category chips)
         │
         ▼
  [views.py: results()]
  Flatten query groups → flat_query string
  Apply DB filters (genre / year / language)
         │
         ├──────────────────────────┐
         ▼                          ▼
  [ai.py: bm25_search()]    [ai.py: semantic_search()]
  BM25Okapi over tokenized  all-MiniLM-L6-v2 cosine
  movie texts; top-50        similarity vs stored
  keyword candidates         embeddings; top-50
         │                          │
         └────────────┬─────────────┘
                      ▼
       [ai.py: reciprocal_rank_fusion()]
       RRF score = Σ 1 / (60 + rank_i)
       Merges both lists → top-20 candidates
                      │
                      ▼
          [ai.py: rerank()]
          cross-encoder/ms-marco-MiniLM-L-6-v2
          Scores (query, movie_text) pairs together
          Returns final top-10 ranked results
                      │
                      ▼
          [views.py] Enrich each result:
          score_pct, rank, matched_keywords, in_watchlist
                      │
                      ▼
          [results.html] Movie grid with:
          - Match badge (#1 · 72%)
          - Keyword tags (dream, heist, mind)

  User clicks "Why this match?"
                      │
                      ▼
          [AJAX → views.py: match_explain()]
                      │
                      ▼
          [ai.py: explain_match_local()]
          FLAN-T5 prompt: query + genre + cast + synopsis
          Output validated (length, echo check)
          Fallback: keyword-overlap template
                      │
                      ▼
          JsonResponse → inline explanation panel
```

**Why three stages instead of one?**

| Approach | Coverage | Accuracy | Speed |
|---|---|---|---|
| BM25 only | Exact terms only | Low for vague queries | Fast |
| Dense only | Semantic meaning | Misses exact names/titles | Medium |
| Cross-encoder on all | Both | High | O(N) — too slow |
| **BM25 + Dense → RRF → Cross-encoder (top-20)** | **Both** | **High** | **Fast** |

The funnel architecture is the production-standard approach in retrieval-augmented systems: cheap broad retrieval narrows the pool, then the expensive but accurate re-ranker is applied only where it's tractable.

---

### 3.5 How Outputs Are Generated and Returned

**Search results:**

The cross-encoder produces a raw logit score for each (query, movie) pair. The view maps this to a 0–100 display percentage and computes matched keywords:

```python
"score_pct": min(100, max(0, int((score + 10) * 5))),
"matched_keywords": sorted(q_tokens & set(tokenize(build_movie_text(movie))))[:6],
```

These values are passed to `_movie_card.html`, which renders:
- A match badge on the poster: `#1 · 72%`
- Keyword tags below the synopsis: `dream  heist  mind`

**Match explanations:**

```python
def explain_match_local(query: str, movie, score: float) -> str:
    # Build a keyword-overlap template as a reliable fallback
    template = f'"{movie.title}" connects to your search through {overlap_str}...'

    # Skip inference for very weak matches
    if score < 0.15:
        return template

    prompt = (
        f"Explain in 2 sentences why the movie '{movie.title}' ({movie.release_year}) "
        f"matches this search query: \"{query}\". "
        f"Movie genre: {movie.genre}. Cast: {cast_preview}. "
        f"Plot summary: {synopsis_snip}"
    )
    pipe   = get_flan_pipeline()
    output = pipe(prompt, max_new_tokens=120, do_sample=False)
    generated = output[0]["generated_text"].strip()

    # Validate before returning
    if len(generated) < 20 or generated.lower().startswith(prompt[:25].lower()):
        return template   # fallback

    return generated
```

The AJAX response is rendered inline in the result card without a page reload.

**Recommendations:**

```python
taste_profile = query_embeddings.mean(axis=0)
score = cosine_similarity(taste_profile.reshape(1,-1), movie_vec.reshape(1,-1))[0][0]
```

The score itself explains the recommendation — no LLM is needed. Template strings provide the displayed reason.

---

### 3.6 Guardrails

| Risk | Implementation |
|---|---|
| Empty query | `results()` returns early with an empty state message before any model is loaded |
| Malformed JSON query groups | `try/except (JSONDecodeError, ValueError)` — falls back to the raw text query |
| No movies in database | Early return with setup instructions before any inference |
| Movie has no embedding | Excluded from `semantic_search()`; still available to BM25 |
| Corrupt embedding JSON | `try/except json.JSONDecodeError` per movie — that movie is skipped |
| Cross-encoder failure | Exception propagates to `search()`, which returns RRF results as fallback |
| FLAN-T5 unavailable / exception | `explain_match_local()` catches all exceptions, logs a warning, returns the template |
| FLAN-T5 output too short (<20 chars) | Validated after generation — falls back to template |
| FLAN-T5 echoes the prompt | Validated (starts-with check) — falls back to template |
| Very weak match (score < 0.15) | FLAN-T5 inference is skipped entirely; template returned immediately |
| BM25 index stale | `_get_bm25_index()` compares current movie PKs to cached PKs; rebuilds if changed |

---

### 3.7 API Comparison

#### What an API-only version would look like

```
User submits query
→ POST to OpenAI Embeddings API  (embed the query)
→ POST to OpenAI Embeddings API  (embed all movie texts, or retrieve from API-hosted index)
→ Cosine rank client-side or via another API call
→ POST to Anthropic / OpenAI Chat API  (generate explanation)
→ Return results
```

Every search triggers 2–3 external API calls. At any meaningful query volume this becomes expensive and slow.

#### Comparison

| Dimension | API-only | Our local system (Option A) |
|---|---|---|
| **Cost per search** | ~$0.05–0.20 (embedding + chat tokens) | $0.00 always |
| **Latency** | 400–1500 ms (network round-trips) | ~50–100 ms (local CPU) |
| **Privacy** | Every query and movie text sent to a third party | Queries never leave the server |
| **Reliability** | Breaks if API is rate-limited, down, or deprecated | Works offline, no external dependency |
| **Model control** | Locked to provider's model versions | Any model can be swapped freely |
| **Cross-encoder re-ranking** | Not available via any mainstream API | Full pipeline — BM25, dense, RRF, cross-encoder |
| **Offline operation** | Impossible | Fully supported |

#### Why we chose Option A

1. **Cost**: The dominant operation (semantic embedding) runs at zero marginal cost regardless of query volume. BM25 has zero inference cost. FLAN-T5 runs at zero cost and is on-click only (not per-search).

2. **Depth**: The cross-encoder re-ranking stage — the most accurate part of the pipeline — has no equivalent in any commercial API. API-based systems are limited to bi-encoder cosine similarity, which the literature consistently shows is significantly less accurate for complex queries.

3. **Privacy**: Movie search queries often include personal details ("movie I watched with my ex", "film about cancer survivor"). Sending these to a third-party API is an unacceptable privacy tradeoff for a user-facing product.

4. **Control**: The model pipeline is fully inspectable and modifiable. Each stage (BM25, dense, RRF, cross-encoder) can be tuned, replaced, or ablated independently without any API dependency.

5. **Offline operation**: The entire system — search, recommendations, explanations — works on a laptop with no internet connection after the initial model download.
