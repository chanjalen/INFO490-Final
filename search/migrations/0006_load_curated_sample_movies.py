from django.db import migrations


def load_curated_sample_movies(apps, schema_editor):
    Movie = apps.get_model("search", "Movie")
    from search.management.commands.load_sample_movies import SAMPLE_MOVIES

    for data in SAMPLE_MOVIES:
        Movie.objects.update_or_create(
            title=data["title"],
            defaults=data,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("search", "0005_backfill_seed_movie_posters"),
    ]

    operations = [
        migrations.RunPython(load_curated_sample_movies, migrations.RunPython.noop),
    ]
