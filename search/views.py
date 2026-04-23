from django.shortcuts import render, get_object_or_404
from .models import Movie


def home(request):
    return render(request, "search/home.html")


def results(request):
    query = request.GET.get("q", "").strip()
    movies = []
    if query:
        movies = Movie.objects.filter(title__icontains=query)
    return render(request, "search/results.html", {"query": query, "movies": movies})


def movie_detail(request, movie_id):
    movie = get_object_or_404(Movie, pk=movie_id)
    return render(request, "search/movie_detail.html", {"movie": movie})
