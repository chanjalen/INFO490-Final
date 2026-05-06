from django.db import migrations


POSTER_REPAIRS = {
    "Eternal Sunshine of the Spotless Mind": "https://image.tmdb.org/t/p/w500/5MwkWH9tYHv3mV9OdYTMR5qreIz.jpg",
    "The Perks of Being a Wallflower": "https://image.tmdb.org/t/p/w500/aKCvdFFF5n80P2VdS7d8YBwbCjh.jpg",
    "Amélie": "https://image.tmdb.org/t/p/w500/nSxDa3M9aMvGVLoItzWTepQ5h5d.jpg",
    "Her": "https://image.tmdb.org/t/p/w500/eCOtqtfvn7mxGl6nfmq4b1exJRc.jpg",
    "Mulholland Drive": "https://image.tmdb.org/t/p/w500/x7A59t6ySylr1L7aubOQEA480vM.jpg",
    "Lost in Translation": "https://image.tmdb.org/t/p/w500/3jCLmYDIIiSMPujbwygNpqdpM8N.jpg",
    "Moonlight": "https://image.tmdb.org/t/p/w500/qLnfEmPrDjJfPyyddLJPkXmshkp.jpg",
    "Portrait of a Lady on Fire": "https://image.tmdb.org/t/p/w500/2LquGwEhbg3soxSCs9VNyh5VJd9.jpg",
    "Drive": "https://image.tmdb.org/t/p/w500/602vevIURmpDfzbnv5Ubi6wIkQm.jpg",
    "Hereditary": "https://image.tmdb.org/t/p/w500/hjlZSXM86wJrfCv5VKfR5DI2VeU.jpg",
    "Brokeback Mountain": "https://image.tmdb.org/t/p/w500/aByfQOQBNa4CMFwIgq3QrqY2ZHh.jpg",
    "Marriage Story": "https://image.tmdb.org/t/p/w500/2JRyCKaRKyJAVpsIHeLvPw5nHmw.jpg",
    "Midsommar": "https://image.tmdb.org/t/p/w500/7LEI8ulZzO5gy9Ww2NVCrKmHeDZ.jpg",
    "Knives Out": "https://image.tmdb.org/t/p/w500/pThyQovXQrw2m0s9x82twj48Jq4.jpg",
    "Moonrise Kingdom": "https://image.tmdb.org/t/p/w500/y4SXcbNl6CEF2t36icuzuBioj7K.jpg",
    "Sorry to Bother You": "https://image.tmdb.org/t/p/w500/peTl1V04E9ppvhgvNmSX0r2ALqO.jpg",
    "The Before Trilogy": "https://image.tmdb.org/t/p/w500/kf1Jb1c2JAOqjuzA3H4oDM263uB.jpg",
    "Clueless": "https://image.tmdb.org/t/p/w500/8AwVTcgpTnmeOs4TdTWqcFDXEsA.jpg",
    "2001: A Space Odyssey": "https://image.tmdb.org/t/p/w500/ve72VxNqjGM69Uky4WTo2bK6rfq.jpg",
    "Inside Out": "https://image.tmdb.org/t/p/w500/2H1TmgdfNtsKlU9jKdeNyYL5y8T.jpg",
    "The Lobster": "https://image.tmdb.org/t/p/w500/7Y9ILV1unpW9mLpGcqyGQU72LUy.jpg",
    "Promising Young Woman": "https://image.tmdb.org/t/p/w500/73QoFJFmUrJfDG2EynFjNc5gJxk.jpg",
}


def repair_poster_urls(apps, schema_editor):
    Movie = apps.get_model("search", "Movie")
    for title, poster_url in POSTER_REPAIRS.items():
        Movie.objects.filter(title=title).update(poster_url=poster_url)


class Migration(migrations.Migration):

    dependencies = [
        ("search", "0006_load_curated_sample_movies"),
    ]

    operations = [
        migrations.RunPython(repair_poster_urls, migrations.RunPython.noop),
    ]
