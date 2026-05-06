import os

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from unittest.mock import patch

from accounts.models import WatchlistItem
from .models import Movie, SearchHistory, SearchRecord
from .gemini import (
    find_search_candidates,
    get_catalog_recommendations,
    get_taste_profile_recommendations,
    rank_search_results,
    _extract_json,
    _extract_ranked_picks,
    _gemini_url,
)
from .ai import get_bi_encoder, tokenize


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

    @override_settings(
        IS_PRODUCTION=False,
        USE_GEMINI=False,
        GEMINI_API_KEY="local-key-should-not-be-used",
    )
    def test_local_search_never_calls_gemini_api_even_with_key(self):
        with patch("search.gemini.requests.post") as mocked_post:
            response = self.client.get(reverse("results"), {"q": "spirit world"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spirited Away")
        mocked_post.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=False,
        GEMINI_API_KEY="",
    )
    def test_production_search_without_gemini_does_not_fall_back_to_local_search(self):
        with patch("search.views.search") as mocked_local_search:
            response = self.client.get(reverse("results"), {"q": "spirit world"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "0 matches found")
        mocked_local_search.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_production_search_uses_gemini_results_only(self):
        movie = Movie.objects.get(title="The Grand Budapest Hotel")
        with (
            patch("search.views.search_with_gemini", return_value=[(movie, 1.0)]) as mocked_gemini,
            patch("search.views.search") as mocked_local_search,
        ):
            response = self.client.get(reverse("results"), {"q": "concierge"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Grand Budapest Hotel")
        mocked_gemini.assert_called_once()
        mocked_local_search.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_gemini_semantic_search_can_rank_vague_query(self):
        with patch("search.gemini._post_gemini", return_value='[{"index": 0, "confidence": 0.93, "reason": "spirit world clue"}]') as mocked_post:
            results = rank_search_results(
                "animated movie where a girl enters a strange spirit bathhouse",
                [Movie.objects.get(title="Spirited Away")],
            )

        prompt = mocked_post.call_args.args[0]
        self.assertIn("integer indexes", prompt)
        self.assertIn("Do not return objects", prompt)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].title, "Spirited Away")
        self.assertAlmostEqual(results[0][1], 0.93)

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_gemini_semantic_search_accepts_index_array(self):
        movies = [
            Movie.objects.get(title="Spirited Away"),
            Movie.objects.get(title="The Grand Budapest Hotel"),
        ]
        with patch("search.gemini._post_gemini", return_value="[1, 0]"):
            results = rank_search_results("a stylish concierge comedy", movies)

        self.assertEqual([movie.title for movie, _ in results], [
            "The Grand Budapest Hotel",
            "Spirited Away",
        ])

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_gemini_semantic_search_recovers_from_truncated_reason_json(self):
        broken = '[{"index": 0, "confidence": 0.91, "reason": "unterminated'
        with patch("search.gemini._post_gemini", return_value=broken):
            results = rank_search_results(
                "women in red dress",
                [Movie.objects.get(title="Spirited Away")],
            )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0].title, "Spirited Away")
        self.assertAlmostEqual(results[0][1], 0.91)

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_production_semantic_search_uses_local_like_guardrail_when_gemini_returns_empty(self):
        target = Movie.objects.create(
            title="Red Dress Mystery",
            synopsis="A woman in a red dress appears at night and changes the course of a chase.",
            genre="Mystery",
            cast="A. Performer",
            release_year=2026,
            language="English",
        )
        other = Movie.objects.get(title="Spirited Away")

        with patch("search.gemini._post_gemini", return_value="[]"):
            results = rank_search_results(
                "General: women in red dree",
                [other, target],
            )

        self.assertTrue(results)
        self.assertEqual(results[0][0], target)

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_gemini_catalog_recommendations_work_without_watchlist(self):
        movies = list(Movie.objects.order_by("title"))
        with patch("search.gemini._post_gemini", return_value='[{"index": 0, "reason": "distinct fantasy discovery pick"}]'):
            results = get_catalog_recommendations(movies, count=12)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], movies[0])
        self.assertEqual(results[0][1], "distinct fantasy discovery pick")

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_gemini_taste_profile_recommendations_compare_genre_cast_synopsis(self):
        movies = list(Movie.objects.order_by("title"))
        with patch("search.gemini._post_gemini", return_value='[{"index": 0, "reason": "matches fantasy tone"}]') as mocked_post:
            results = get_taste_profile_recommendations(
                ["Recent search: magical fantasy journey"],
                movies,
                count=6,
            )

        prompt = mocked_post.call_args.args[0]
        self.assertIn("genre, cast, synopsis", prompt)
        self.assertIn("Recent search: magical fantasy journey", prompt)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], movies[0])

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_production_recommendations_use_catalog_gemini_without_watchlist(self):
        movie = Movie.objects.get(title="Spirited Away")
        with (
            patch("search.views.get_catalog_recommendations", return_value=[(movie, "A broad catalog pick.")]) as mocked_catalog,
            patch("search.views.get_taste_profile_recommendations") as mocked_profile,
            patch("search.views.get_recommendations") as mocked_local_recs,
        ):
            response = self.client.get(reverse("recommended"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spirited Away")
        self.assertContains(response, "discovery picks curated")
        mocked_profile.assert_not_called()
        mocked_catalog.assert_called_once()
        self.assertEqual(mocked_catalog.call_args.kwargs["count"], 24)
        mocked_local_recs.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_production_recommendations_use_gemini_taste_profile_from_watchlist(self):
        user = User.objects.create_user(username="prod-watchlist-user", password="pass12345")
        watched = Movie.objects.get(title="Spirited Away")
        recommended_movie = Movie.objects.get(title="The Grand Budapest Hotel")
        WatchlistItem.objects.create(user=user, movie=watched)
        self.client.force_login(user)

        with (
            patch("search.views.get_taste_profile_recommendations", return_value=[(recommended_movie, "Matches the watchlist mood.")]) as mocked_profile,
            patch("search.views.get_watchlist_recommendations") as mocked_watchlist,
            patch("search.views.get_catalog_recommendations") as mocked_catalog,
            patch("search.views.get_recommendations") as mocked_local_recs,
        ):
            response = self.client.get(reverse("recommended"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Grand Budapest Hotel")
        self.assertContains(response, "based on your watchlist")
        mocked_profile.assert_called_once()
        self.assertIn("Genre: Fantasy", mocked_profile.call_args.args[0][0])
        self.assertIn("Cast: Rumi Hiiragi", mocked_profile.call_args.args[0][0])
        self.assertIn("Synopsis:", mocked_profile.call_args.args[0][0])
        self.assertEqual(mocked_profile.call_args.kwargs["count"], 24)
        mocked_watchlist.assert_not_called()
        mocked_catalog.assert_not_called()
        mocked_local_recs.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=True,
        GEMINI_API_KEY="production-key",
    )
    def test_production_recommendations_use_gemini_taste_profile_from_history(self):
        user = User.objects.create_user(username="prod-history-user", password="pass12345")
        recommended_movie = Movie.objects.get(title="Spirited Away")
        SearchHistory.objects.create(
            user=user,
            query_text="Fantasy stories with a young girl in a magical world",
            result_count=3,
        )
        self.client.force_login(user)

        with (
            patch("search.views.get_taste_profile_recommendations", return_value=[(recommended_movie, "Matches recent fantasy searches.")]) as mocked_profile,
            patch("search.views.get_catalog_recommendations") as mocked_catalog,
            patch("search.views.get_recommendations") as mocked_local_recs,
        ):
            response = self.client.get(reverse("recommended"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spirited Away")
        mocked_profile.assert_called_once()
        self.assertIn("Recent search: Fantasy stories", mocked_profile.call_args.args[0][0])
        mocked_catalog.assert_not_called()
        mocked_local_recs.assert_not_called()

    @override_settings(
        IS_PRODUCTION=False,
        USE_GEMINI=False,
        GEMINI_API_KEY="local-key-should-not-be-used",
    )
    def test_local_recommendations_never_call_gemini_api_even_with_key(self):
        user = User.objects.create_user(username="local-rec-user", password="pass12345")
        movie = Movie.objects.get(title="Spirited Away")
        WatchlistItem.objects.create(user=user, movie=movie)
        self.client.force_login(user)

        with patch("search.gemini.requests.post") as mocked_post:
            response = self.client.get(reverse("recommended"))

        self.assertEqual(response.status_code, 200)
        mocked_post.assert_not_called()

    @override_settings(
        IS_PRODUCTION=True,
        USE_GEMINI=False,
        GEMINI_API_KEY="",
    )
    def test_production_recommendations_without_gemini_do_not_use_local_tiers(self):
        user = User.objects.create_user(username="prod-rec-user", password="pass12345")
        movie = Movie.objects.get(title="Spirited Away")
        WatchlistItem.objects.create(user=user, movie=movie)
        self.client.force_login(user)

        with patch("search.views.get_recommendations") as mocked_local_recs:
            response = self.client.get(reverse("recommended"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nothing to show yet.")
        mocked_local_recs.assert_not_called()

    @override_settings(
        IS_PRODUCTION=False,
        USE_GEMINI=False,
        GEMINI_API_KEY="local-key-should-not-be-used",
    )
    def test_gemini_helper_is_inert_when_not_enabled(self):
        with patch("search.gemini.requests.post") as mocked_post:
            candidates = find_search_candidates("spirit world", list(Movie.objects.all()))

        self.assertEqual(candidates, [])
        mocked_post.assert_not_called()

    def test_local_model_cache_settings_are_configured(self):
        self.assertTrue(str(settings.LOCAL_MODEL_CACHE_DIR).endswith(".model-cache"))
        self.assertIn(".model-cache", settings.LOCAL_MODEL_CACHE_DIR.as_posix())
        self.assertEqual(os.environ.get("HF_HUB_OFFLINE"), "1")
        self.assertEqual(os.environ.get("TRANSFORMERS_OFFLINE"), "1")

    def test_gemini_uses_stable_configurable_model(self):
        self.assertEqual(settings.GEMINI_MODEL, "gemini-2.5-flash")
        self.assertIn("/models/gemini-2.5-flash:generateContent", _gemini_url())

    @override_settings(GEMINI_MODEL="gemini-2.5-flash-preview-04-17")
    def test_gemini_ignores_stale_render_model_env(self):
        self.assertIn("/models/gemini-2.5-flash:generateContent", _gemini_url())
        self.assertNotIn("preview", _gemini_url())

    def test_gemini_json_parser_accepts_wrapped_json(self):
        wrapped = 'Here are the picks:\n```json\n[{"index": 0, "reason": "match"}]\n```'
        self.assertEqual(_extract_json(wrapped)[0]["index"], 0)

    def test_gemini_ranked_pick_parser_recovers_indexes_from_bad_json(self):
        broken = '[{"index": 4, "confidence": 0.82, "reason": "cut off'
        self.assertEqual(_extract_ranked_picks(broken)[0]["index"], 4)

    def test_tokenizer_normalizes_common_visual_query_terms(self):
        self.assertIn("woman", tokenize("women in red dree"))
        self.assertIn("dress", tokenize("women in red dree"))

    @override_settings(LOCAL_DENSE_ENABLED=False)
    def test_local_dense_models_are_opt_in(self):
        self.assertIsNone(get_bi_encoder())

    def test_movie_detail_page_loads(self):
        movie = Movie.objects.filter(title="Spirited Away").first()
        response = self.client.get(reverse("movie_detail", args=[movie.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, movie.title)

    def test_curated_sample_movies_have_poster_urls(self):
        movie = Movie.objects.get(title="Inception")
        self.assertTrue(movie.poster_url.startswith("https://image.tmdb.org/t/p/w500/"))
        response = self.client.get(reverse("movie_detail", args=[movie.pk]))
        self.assertContains(response, f'src="{movie.poster_url}"')

    def test_portrait_of_a_lady_on_fire_uses_valid_repaired_poster_path(self):
        movie = Movie.objects.get(title="Portrait of a Lady on Fire")
        self.assertEqual(
            movie.poster_url,
            "https://image.tmdb.org/t/p/w500/2LquGwEhbg3soxSCs9VNyh5VJd9.jpg",
        )
        self.assertNotIn("3NTAbAiao4JLzFsBE6jVNUsEDv4", movie.poster_url)

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

    def test_analytics_keywords_filter_query_structure_labels(self):
        user = User.objects.create_user(username="analytics-user", password="pass12345")
        SearchRecord.objects.create(
            user=user,
            query="Character: lonely wizard; Scene: rainy station; Plot: hidden memory",
            focus="Character",
            result_count=2,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("analytics_data"))
        self.assertEqual(response.status_code, 200)
        words = {item["word"] for item in response.json()["keywords"]}

        self.assertTrue({"lonely", "wizard", "rainy", "station", "hidden", "memory"} & words)
        self.assertNotIn("character", words)
        self.assertNotIn("scene", words)
        self.assertNotIn("plot", words)
