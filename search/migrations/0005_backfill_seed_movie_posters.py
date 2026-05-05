from django.db import migrations


POSTER_DATA = {
    "Spirited Away": {
        "poster_url": "https://image.tmdb.org/t/p/w500/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg",
        "tmdb_id": 129,
    },
    "The Grand Budapest Hotel": {
        "poster_url": "https://image.tmdb.org/t/p/w500/eWdyYQreja6JGCzqHWXpWHDrrPo.jpg",
        "tmdb_id": 120467,
    },
    "Parasite": {
        "poster_url": "https://image.tmdb.org/t/p/w500/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
        "tmdb_id": 496243,
    },
    "In the Mood for Love": {
        "poster_url": "https://image.tmdb.org/t/p/w500/iYypPT4bhqXfq1b6EnmxvRt6b2Y.jpg",
        "tmdb_id": 843,
    },
    "Memories of Murder": {
        "poster_url": "https://image.tmdb.org/t/p/w500/dsEoTJKM1s5OVDkS2P2JdoTxo4K.jpg",
        "tmdb_id": 11423,
    },
    "Arrival": {
        "poster_url": "https://image.tmdb.org/t/p/w500/pEzNVQfdzYDzVK0XqxERIw2x2se.jpg",
        "tmdb_id": 329865,
    },
    "Pan's Labyrinth": {
        "poster_url": "https://image.tmdb.org/t/p/w500/z7xXihu5wHuSMWymq5VAulPVuvg.jpg",
        "tmdb_id": 1417,
    },
    "Before Sunrise": {
        "poster_url": "https://image.tmdb.org/t/p/w500/kf1Jb1c2JAOqjuzA3H4oDM263uB.jpg",
        "tmdb_id": 76,
    },
}


def backfill_posters(apps, schema_editor):
    Movie = apps.get_model("search", "Movie")
    for title, data in POSTER_DATA.items():
        for movie in Movie.objects.filter(title=title):
            movie.poster_url = data["poster_url"]
            tmdb_id = data["tmdb_id"]
            if not Movie.objects.exclude(pk=movie.pk).filter(tmdb_id=tmdb_id).exists():
                movie.tmdb_id = tmdb_id
                movie.save(update_fields=["poster_url", "tmdb_id"])
            else:
                movie.save(update_fields=["poster_url"])


def clear_seed_posters(apps, schema_editor):
    Movie = apps.get_model("search", "Movie")
    Movie.objects.filter(title__in=POSTER_DATA.keys()).update(
        poster_url="",
        tmdb_id=None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("search", "0004_searchrecord"),
    ]

    operations = [
        migrations.RunPython(backfill_posters, clear_seed_posters),
    ]
