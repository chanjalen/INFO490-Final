from django.conf import settings
from django.db import models
from django.contrib.auth.models import User


class Movie(models.Model):
    title = models.CharField(max_length=255)
    tagline = models.CharField(max_length=255, blank=True)
    synopsis = models.TextField(blank=True)
    genre = models.CharField(max_length=100, blank=True)
    cast = models.TextField(blank=True)
    director = models.CharField(max_length=150, blank=True)
    release_year = models.IntegerField(null=True, blank=True)
    language = models.CharField(max_length=50, blank=True)
    poster_url = models.URLField(blank=True)
    tmdb_id = models.IntegerField(null=True, blank=True, unique=True)
    embedding = models.TextField(blank=True)

    class Meta:
        ordering = ["-release_year", "title"]

    def __str__(self):
        return f"{self.title} ({self.release_year})"

    @property
    def genre_list(self) -> list[str]:
        return [g.strip() for g in self.genre.split(",") if g.strip()]

    @property
    def cast_list(self) -> list[str]:
        return [c.strip() for c in self.cast.split(",") if c.strip()]


class SearchRecord(models.Model):
    """Lightweight per-search record used by the analytics dashboard."""
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


class SearchHistory(models.Model):
    """Full search history record used by the AI recommendation pipeline."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="search_history")
    query_text = models.TextField()
    query_groups = models.JSONField(default=dict, blank=True)
    result_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Search histories"

    def __str__(self):
        return f'{self.user.username}: "{self.query_text[:60]}"'
