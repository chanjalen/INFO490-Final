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
