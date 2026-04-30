from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("results/", views.results, name="results"),
    path("history/", views.history, name="history"),
    path("recommended/", views.recommended, name="recommended"),
    path("movie/<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("analytics/", views.analytics, name="analytics"),
    path("analytics/data/", views.analytics_data, name="analytics_data"),
]
