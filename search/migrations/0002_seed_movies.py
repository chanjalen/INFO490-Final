# Generated manually for demo content.

from django.db import migrations


SAMPLE_MOVIES = [
    {
        "title": "Spirited Away",
        "synopsis": "A ten-year-old girl enters a world of spirits and must work with unusual allies to rescue her parents and find her way home.",
        "genre": "Fantasy",
        "cast": "Rumi Hiiragi, Miyu Irino",
        "release_year": 2001,
        "language": "Japanese",
        "poster_url": "",
    },
    {
        "title": "The Grand Budapest Hotel",
        "synopsis": "A meticulous concierge and his lobby boy become entangled in a murder mystery, a priceless painting, and the collapse of an old European world.",
        "genre": "Comedy / Adventure",
        "cast": "Ralph Fiennes, Tony Revolori",
        "release_year": 2014,
        "language": "English",
        "poster_url": "",
    },
    {
        "title": "Parasite",
        "synopsis": "A struggling family infiltrates a wealthy household through a series of calculated deceptions, only to trigger a volatile class collision.",
        "genre": "Thriller / Drama",
        "cast": "Song Kang-ho, Choi Woo-shik, Park So-dam",
        "release_year": 2019,
        "language": "Korean",
        "poster_url": "",
    },
    {
        "title": "In the Mood for Love",
        "synopsis": "Two neighbors form a deep bond after suspecting their spouses of infidelity, navigating longing and restraint in 1960s Hong Kong.",
        "genre": "Romance / Drama",
        "cast": "Tony Leung, Maggie Cheung",
        "release_year": 2000,
        "language": "Cantonese",
        "poster_url": "",
    },
    {
        "title": "Memories of Murder",
        "synopsis": "Detectives in rural South Korea confront fear, uncertainty, and institutional limits while pursuing a serial killer.",
        "genre": "Crime / Thriller",
        "cast": "Song Kang-ho, Kim Sang-kyung",
        "release_year": 2003,
        "language": "Korean",
        "poster_url": "",
    },
    {
        "title": "Arrival",
        "synopsis": "A linguist works to communicate with mysterious visitors whose language may alter humanity's understanding of time itself.",
        "genre": "Science Fiction / Drama",
        "cast": "Amy Adams, Jeremy Renner",
        "release_year": 2016,
        "language": "English",
        "poster_url": "",
    },
    {
        "title": "Pan's Labyrinth",
        "synopsis": "During the aftermath of war, a young girl escapes into a dark fairytale realm filled with dangerous creatures and moral tests.",
        "genre": "Fantasy / War",
        "cast": "Ivana Baquero, Sergi Lopez",
        "release_year": 2006,
        "language": "Spanish",
        "poster_url": "",
    },
    {
        "title": "Before Sunrise",
        "synopsis": "Two strangers meet on a train and spend one unforgettable night exploring Vienna and each other through conversation.",
        "genre": "Romance",
        "cast": "Ethan Hawke, Julie Delpy",
        "release_year": 1995,
        "language": "English",
        "poster_url": "",
    },
]


def seed_movies(apps, schema_editor):
    Movie = apps.get_model("search", "Movie")
    for movie_data in SAMPLE_MOVIES:
        Movie.objects.get_or_create(title=movie_data["title"], defaults=movie_data)
class Migration(migrations.Migration):
    dependencies = [
        ("search", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_movies, migrations.RunPython.noop),
    ]
