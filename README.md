# SoClose

SoClose is a Django movie discovery app for finding films from vague memories, scene clues, moods, characters, quotes, and visual details. It is organized into two Django apps:

- `search`: movie search, results, recommendations, history, analytics, AI search logic, and movie data commands.
- `accounts`: signup, login, logout, profiles, account updates, and watchlist management.

The app uses SQLite for local development and PostgreSQL on Render when `DATABASE_URL` is configured. TMDB is used as an external movie metadata source; it is not the application database.

## Dependencies

Core dependencies are listed in `requirements.txt`:

- Django
- python-dotenv
- gunicorn
- WhiteNoise
- rank-bm25
- requests
- dj-database-url
- psycopg2-binary

Optional local AI dependencies are listed in `requirements-dev.txt`:

- sentence-transformers
- transformers
- scikit-learn
- numpy

Use `requirements.txt` for the deployed Render app. Use `requirements-dev.txt` locally only if you want to run the optional local dense models and FLAN-T5 explanation pipeline.

## Setup Instructions

1. Create and activate a virtual environment.

   PowerShell:

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   macOS/Linux:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies.

   Core app only:

   ```bash
   pip install -r requirements.txt
   ```

   Core app plus optional local AI models:

   ```bash
   pip install -r requirements-dev.txt
   ```

3. Create a local `.env` file.

   ```env
   SECRET_KEY=dev-only-secret-key
   DEBUG=True
   APP_ENV=local
   ALLOWED_HOSTS=localhost,127.0.0.1
   TMDB_API_KEY=
   GEMINI_API_KEY=
   LOCAL_DENSE_ENABLED=False
   FLAN_T5_ENABLED=False
   ```

   Notes:

   - `TMDB_API_KEY` is only needed if you run `fetch_tmdb_movies`.
   - `GEMINI_API_KEY` is only needed for production Gemini behavior.
   - Local mode does not call Gemini.
   - Set `LOCAL_DENSE_ENABLED=True` only after the local model files are installed in the cache.

4. Run migrations.

   ```bash
   python manage.py migrate
   ```

5. Load movie data.

   Quick curated dataset:

   ```bash
   python manage.py load_sample_movies
   ```

   Optional larger TMDB import:

   ```bash
   python manage.py fetch_tmdb_movies
   ```

   The TMDB import command is designed to expand the catalog toward a much larger movie database, depending on the number of pages fetched and API availability. The checked local database is not guaranteed to contain the full 15,000-movie target.

6. Optional: precompute local embeddings.

   This requires `requirements-dev.txt`, cached sentence-transformer models, and `LOCAL_DENSE_ENABLED=True`.

   ```bash
   python manage.py embed_movies
   ```

## How to Run the App Locally

Start the Django development server:

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

Useful routes:

| URL | Purpose |
| --- | --- |
| `/` | Main search page |
| `/results/?q=<query>` | Search results |
| `/movie/<id>/` | Movie detail page |
| `/recommended/` | Personalized recommendations |
| `/history/` | Search history |
| `/analytics/` | Search analytics dashboard |
| `/analytics/data/` | Internal JSON API for analytics |
| `/watchlist/` | User watchlist |
| `/login/` | Login |
| `/signup/` | Signup |
| `/admin/` | Django admin |

## Where to Access the AI Feature

The main AI feature is part of the normal user flow.

1. Go to `/`.
2. Enter a vague movie clue, such as `woman in red dress`, `a girl enters a spirit world`, or `night scene in a small town`.
3. Optionally choose a focus category such as Character, Scene, Plot, Dialogue, or Visual.
4. Submit the search.
5. Results appear at `/results/` as ranked movie cards with match percentages.

The recommendation AI feature is available at:

```text
/recommended/
```

It uses watchlist items, search history, session activity, genre, cast, and synopsis signals to recommend movies. In production, this route uses Gemini when configured. Locally, it uses local/session-based recommendation logic and falls back to editorial defaults when there is not enough user history.

The optional explanation feature is available from:

```text
/movie/<id>/explain/
```

This endpoint is login-protected and returns a JSON explanation for why a result matches the user's query. If FLAN-T5 is disabled or unavailable, the app returns a template-based explanation instead.

## Production on Render

Render build command:

```bash
bash build.sh
```

Render start command:

```bash
bash start.sh
```

Do not include `web:` in the Render dashboard start command. `web:` belongs only in `Procfile`.

Important production environment variables:

```env
SECRET_KEY=<set by Render>
DEBUG=False
APP_ENV=production
ALLOWED_HOSTS=.onrender.com
DATABASE_URL=<Render PostgreSQL connection string>
GEMINI_API_KEY=<Gemini API key>
GEMINI_MODEL=gemini-2.5-flash
FLAN_T5_ENABLED=False
```

In production, SoClose uses PostgreSQL, WhiteNoise static files, Gunicorn, and Gemini-powered semantic search/recommendations. `start.sh` runs `prepare_render` before Gunicorn so migrations, curated sample data, and poster repair logic are applied before traffic reaches the app.

## Tests

Run the Django test suite:

```bash
python manage.py test
```

The tests cover local-vs-production AI routing, Gemini parsing guardrails, recommendation behavior, poster URL repair, Render startup commands, tokenizer normalization, and core page behavior.
