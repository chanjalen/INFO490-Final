import json

from django.contrib.auth import (
    authenticate,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .forms import (
    DeleteAccountForm,
    DisplayNameForm,
    EmailUpdateForm,
    PasswordChangeForm,
    SignupForm,
)
from .models import UserProfile, WatchlistItem


# ── Public auth views ─────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    error = None
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(request.GET.get("next") or "home")
        error = "Invalid username or password."
    else:
        form = AuthenticationForm()
    return render(request, "accounts/login.html", {"form": form, "error": error})


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.contrib.auth.models import User
        from django.db import IntegrityError
        try:
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email", ""),
                password=form.cleaned_data["password"],
            )
        except IntegrityError:
            form.add_error("username", "That username is already taken.")
            return render(request, "accounts/signup.html", {"form": form})
        login(request, user)
        return redirect("home")
    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


# ── Profile AJAX endpoints (login required) ───────────────────────────────

def _json_errors(form):
    """Flatten form errors to a simple {field: [msg, ...]} dict."""
    return {field: list(errs) for field, errs in form.errors.items()}


@login_required
@require_POST
def update_display_name(request):
    form = DisplayNameForm(request.POST)
    if form.is_valid():
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        profile.display_name = form.cleaned_data["display_name"]
        profile.save()
        return JsonResponse(
            {
                "ok": True,
                "display_name": profile.get_display_name(),
                "initials": profile.get_initials(),
            }
        )
    return JsonResponse({"ok": False, "errors": _json_errors(form)}, status=400)


@login_required
@require_POST
def update_email(request):
    form = EmailUpdateForm(request.POST, instance=request.user)
    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True, "email": request.user.email})
    return JsonResponse({"ok": False, "errors": _json_errors(form)}, status=400)


@login_required
@require_POST
def update_password(request):
    form = PasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)  # keep user logged in
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "errors": _json_errors(form)}, status=400)


@login_required
@require_POST
def delete_account(request):
    form = DeleteAccountForm(request.POST)
    if form.is_valid():
        user = request.user
        logout(request)
        user.delete()
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False, "errors": _json_errors(form)}, status=400)


# ── Watchlist ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_watchlist(request, movie_id):
    from django.shortcuts import get_object_or_404
    from search.models import Movie

    movie = get_object_or_404(Movie, pk=movie_id)
    item, created = WatchlistItem.objects.get_or_create(
        user=request.user, movie=movie
    )
    if not created:
        item.delete()
        in_list = False
    else:
        in_list = True
    count = request.user.watchlist.count()
    return JsonResponse({"ok": True, "in_list": in_list, "count": count})


@login_required
def watchlist_page(request):
    items = (
        WatchlistItem.objects.filter(user=request.user)
        .select_related("movie")
    )
    watchlist_ids = set(items.values_list("movie_id", flat=True))
    return render(
        request,
        "accounts/watchlist.html",
        {
            "active_page": "watchlist",
            "items": items,
            "watchlist_ids": watchlist_ids,
        },
    )
