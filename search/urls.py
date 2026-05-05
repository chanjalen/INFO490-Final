from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("results/", views.results, name="results"),
    path("movie/<int:pk>/", views.movie_detail, name="movie_detail"),
    path("history/", views.history, name="history"),
    path("history/clear/", views.clear_history, name="clear_history"),
    path("recommended/", views.recommended, name="recommended"),
    path("analytics/", views.analytics, name="analytics"),
    path("analytics/data/", views.analytics_data, name="analytics_data"),
    path("movie/<int:pk>/explain/", views.match_explain, name="match_explain"),
    path("movie/<int:pk>/watchlist/", views.toggle_watchlist, name="toggle_watchlist"),
    path("watchlist/", views.watchlist_view, name="watchlist"),
]
