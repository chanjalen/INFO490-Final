from django.contrib import admin

from .models import Movie


@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display = ("title", "release_year", "genre", "language")
    list_filter = ("genre", "language", "release_year")
    search_fields = ("title", "synopsis", "cast", "genre", "language")
