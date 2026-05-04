# MovieFinder

A Django web app for searching movies by title. Built for Info 490 Final Project.

## Tech Stack

- Python 3.13
- Django 6.0
- SQLite (development database)
- python-dotenv (environment variable management)

## Project Structure

```
Info490 Final/
├── moviefinder/          # Django project config
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── search/               # Main app
│   ├── models.py         # Movie model
│   ├── views.py          # home, results, movie_detail
│   ├── urls.py           # app URL routes
│   ├── ai.py             # full AI pipeline
│   ├── templates/
│   │   └── search/
│   │       ├── base.html
│   │       ├── home.html
│   │       ├── results.html
│   │       └── movie_detail.html
│   └── migrations/
├── static/               # Static files (CSS, JS, images)
├── db.sqlite3            # SQLite database
├── manage.py
├── requirements.txt
├── .env                  # Local environment variables (not committed)
└── .env.example          # Template for .env
```

## Setup

1. **Clone the repo and create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   Key packages:

   - `Django>=6.0` — web framework
   - `rank-bm25>=0.2.2` — keyword retrieval (Stage 1a)
   - `sentence-transformers>=3.0.0` — bi-encoder embeddings and cross-encoder re-ranking (Stages 1b, 2)
   - `transformers>=4.40.0` — FLAN-T5 local text generation (Stage 3)
   - `scikit-learn>=1.4.0` — cosine similarity
   - `numpy>=1.26.0` — vector math
   - `requests>=2.31.0` — TMDB API fetching (setup only)
   - `python-dotenv` — environment variable management

AI models are downloaded automatically from Hugging Face on first use and cached locally (~360 MB total). No GPU required — all inference runs on CPU.

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and fill in your SECRET_KEY & TMBD_API_KEY
   ```
   **Getting a TMDB API key (free, takes 2 minutes):**
   1. Create an account at [themoviedb.org/signup](https://www.themoviedb.org/signup)
   2. Go to [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
   3. Request an API Key → choose **Developer** (instant approval)
   4. Copy the **API Key (v3 auth)** value into your `.env`


4. **Load Movie Data**

   **Option A — Full dataset via TMDB (~15,000 movies, recommended)**
      ```bash
      python manage.py fetch_tmdb_movies
      ```
   This runs two discovery passes against the TMDB API and fetches full details (cast, tagline, genres, director) for each film. Takes approximately 10–15 minutes. Run with `--resume` to continue an interrupted fetch.
   
   **Option B — Sample dataset (45 movies, for quick testing)**
      ```bash
      python manage.py load_sample_movies
      ```

5. **Pre-compute AI embeddings**
   ```bash
   python manage.py embed_movies
   ```

This runs every movie through the local sentence-transformer model and stores the resulting vector in the database. Takes approximately 15 minutes for 15,000 movies on CPU. Only needs to be run once, and again only when new movies are added.

6. **Run migrations**
   ```bash
   python manage.py migrate
   ```

7. **Start the development server**
   ```bash
   python manage.py runserver
   ```

   App will be available at `http://127.0.0.1:8000/`

## How to Run the App

| URL                    | Page                 | Description                             |
|------------------------|----------------------|-----------------------------------------|
| `/`                    | Home / Search        | Query builder with category chips       |
| `/results/?q=<query>`  | Search Results       | AI-ranked movie cards with match scores |
| `/movie/<id>/`         | Movie Detail         | Full movie info                         |
| `/movie/<id>/explain/` | Match Explain (AJAX) | Why this film matches your query        |
| `/recommended/`        | Recommended For You  | Personalized daily recommendations      |
| `/history/`            | Search History       | Past searches with re-run and delete    |
| `/watchlist/`          | Watchlist            | Saved films                             |
| `/admin/`              | Django Admin         | Database management                     |

## Where to Access the AI Features

All AI features are part of the live user flow, none require separate scripts or notebooks.

**Semantic + Keyword Hybrid Search**
Navigate to the home page at `/`. Type a description in the search box — this can be a character name, a scene description, a mood, a quote, or any combination. Use the category chips (Character, Scene, Plot, Dialogue, Visual) to add structured query groups. Click **Search**. Results at `/results/` are ranked by a three-stage AI pipeline: BM25 keyword retrieval and dense semantic search run in parallel, their results are merged with Reciprocal Rank Fusion, and a cross-encoder model produces the final ranking.

**Match Explanation Panel**
On any search results page, click **"Why this match?"** on a result card. A locally-generated explanation (FLAN-T5) appears inline explaining the specific connection between your query and that film. This is the only feature with a slight delay (~1–2 seconds) as the model runs inference on CPU.

**Personalized Recommendations**
Navigate to `/recommended/` via the top navigation bar. The system reads your last 10 searches, encodes them as embedding vectors, averages them into a single taste-profile vector, and returns the 6 most similar films in the database. If you have no search history yet, an editorial default set is shown.


## Environment Variables

| Variable        | Description                   | Default                                                    |
|-----------------|-------------------------------|------------------------------------------------------------|
| `SECRET_KEY`    | Django secret key             | required                                                   |
| `TMDB_API_KEY`  | For data fetch only           | Used by `fetch_tmdb_movies` command, not needed at runtime |
| `DEBUG`         | Enable debug mode             | `False`                                                    |
| `ALLOWED_HOSTS` | Comma-separated list of hosts | `localhost,127.0.0.1`                                      |

## URL Routes

| URL                   | View           | Description           |
|-----------------------|----------------|-----------------------|
| `/`                   | `home`         | Search landing page   |
| `/results/?q=<query>` | `results`      | Search results        |
| `/movie/<id>/`        | `movie_detail` | Individual movie page |
| `/admin/`             | Django admin   | Admin panel           |

## Movie Model Fields

| Field          | Type         | Notes    |
|----------------|--------------|----------|
| `title`        | CharField    | Required |
| `synopsis`     | TextField    | Optional |
| `genre`        | CharField    | Optional |
| `cast`         | TextField    | Optional |
| `release_year` | IntegerField | Optional |
| `language`     | CharField    | Optional |
| `poster_url`   | URLField     | Optional |
