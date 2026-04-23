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

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env and fill in your SECRET_KEY
   ```

4. **Run migrations**
   ```bash
   python manage.py migrate
   ```

5. **Start the development server**
   ```bash
   python manage.py runserver
   ```

   App will be available at `http://127.0.0.1:8000/`

## Environment Variables

| Variable        | Description                        | Default         |
|-----------------|------------------------------------|-----------------|
| `SECRET_KEY`    | Django secret key                  | required        |
| `DEBUG`         | Enable debug mode                  | `False`         |
| `ALLOWED_HOSTS` | Comma-separated list of hosts      | `localhost,127.0.0.1` |

## URL Routes

| URL                  | View           | Description            |
|----------------------|----------------|------------------------|
| `/`                  | `home`         | Search landing page    |
| `/results/?q=<query>`| `results`      | Search results         |
| `/movie/<id>/`       | `movie_detail` | Individual movie page  |
| `/admin/`            | Django admin   | Admin panel            |

## Movie Model Fields

| Field          | Type        | Notes                  |
|----------------|-------------|------------------------|
| `title`        | CharField   | Required               |
| `synopsis`     | TextField   | Optional               |
| `genre`        | CharField   | Optional               |
| `cast`         | TextField   | Optional               |
| `release_year` | IntegerField| Optional               |
| `language`     | CharField   | Optional               |
| `poster_url`   | URLField    | Optional               |
