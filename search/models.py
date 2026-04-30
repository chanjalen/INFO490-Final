from django.conf import settings
from django.db import models


class Movie(models.Model):
    title = models.CharField(max_length=255)
    synopsis = models.TextField(blank=True)
    genre = models.CharField(max_length=100, blank=True)
    cast = models.TextField(blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, blank=True)
    poster_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.title} ({self.release_year})"


class SearchRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="search_records",
    )
    query = models.CharField(max_length=500, blank=True)
    focus = models.CharField(max_length=100, blank=True)
    genre = models.CharField(max_length=100, blank=True)
    language = models.CharField(max_length=50, blank=True)
    year = models.CharField(max_length=10, blank=True)
    result_count = models.IntegerField(default=0)
    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-searched_at"]

    def __str__(self):
        return f"{self.user.username}: {self.query or '(filters only)'} @ {self.searched_at:%Y-%m-%d %H:%M}"
