from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/",  views.login_view,  name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    # Profile AJAX endpoints
    path("profile/display-name/", views.update_display_name, name="update_display_name"),
    path("profile/email/",        views.update_email,        name="update_email"),
    path("profile/password/",     views.update_password,     name="update_password"),
    path("profile/delete/",       views.delete_account,      name="delete_account"),
    # Watchlist
    path("watchlist/",                        views.watchlist_page,    name="watchlist"),
    path("watchlist/toggle/<int:movie_id>/",  views.toggle_watchlist,  name="toggle_watchlist"),
]
