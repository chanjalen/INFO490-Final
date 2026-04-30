from django.contrib.auth.models import User
from django.db import models
from search.models import Movie


class UserProfile(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    display_name = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return self.display_name or self.user.username

    def get_display_name(self):
        return self.display_name or self.user.username

    def get_initials(self):
        name = self.get_display_name()
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return name[:2].upper() if name else "?"


class WatchlistItem(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="watchlist"
    )
    movie = models.ForeignKey(
        Movie, on_delete=models.CASCADE, related_name="watchlisted_by"
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "movie")
        ordering = ["-added_at"]

    def __str__(self):
        return f"{self.user.username} → {self.movie.title}"
