from django.test import TestCase
from django.urls import reverse

from .models import Movie


class SearchViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Movie.objects.update_or_create(
            title="Spirited Away",
            defaults={
                "synopsis": "A young girl wanders into a spirit world and works to save her parents.",
                "genre": "Fantasy",
                "cast": "Rumi Hiiragi, Miyu Irino",
                "release_year": 2001,
                "language": "Japanese",
            },
        )
        Movie.objects.update_or_create(
            title="The Grand Budapest Hotel",
            defaults={
                "synopsis": "A concierge and lobby boy race across Europe during a dangerous inheritance dispute.",
                "genre": "Comedy / Adventure",
                "cast": "Ralph Fiennes, Tony Revolori",
                "release_year": 2014,
                "language": "English",
            },
        )

    def test_home_page_loads(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Semantic film intelligence")

    def test_results_searches_multiple_fields(self):
        response = self.client.get(reverse("results"), {"q": "spirit world"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spirited Away")

    def test_year_in_query_does_not_match_every_movie_from_that_year(self):
        Movie.objects.create(
            title="Completely Different 2016",
            synopsis="No aliens or linguistics here.",
            genre="Drama",
            cast="Someone Else",
            release_year=2016,
            language="English",
        )
        response = self.client.get(reverse("results"), {"q": "arrival 2016"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Arrival")
        self.assertNotContains(response, "Completely Different 2016")

    def test_results_records_search_history(self):
        self.client.get(reverse("results"), {"q": "concierge"})
        history = self.client.session["search_history_v1"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["query"], "concierge")

    def test_history_page_loads(self):
        self.client.get(reverse("results"), {"q": "spirited"})
        response = self.client.get(reverse("history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Search History")
        self.assertContains(response, "spirited")

    def test_recommended_page_loads(self):
        self.client.get(reverse("results"), {"q": "Fantasy", "genre": "Fantasy"})
        response = self.client.get(reverse("recommended"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recommendations")

    def test_movie_detail_page_loads(self):
        movie = Movie.objects.filter(title="Spirited Away").first()
        response = self.client.get(reverse("movie_detail", args=[movie.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movie.title)

    def test_movie_detail_with_blank_genre_shows_no_related_titles(self):
        primary = Movie.objects.create(
            title="No Genre Primary",
            synopsis="Primary movie with blank genre.",
            genre="",
            cast="Lead Actor",
            release_year=2025,
            language="English",
        )
        Movie.objects.create(
            title="No Genre Unrelated",
            synopsis="This should not appear as related.",
            genre="Action",
            cast="Another Actor",
            release_year=2024,
            language="English",
        )
        response = self.client.get(reverse("movie_detail", args=[primary.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Related titles")
