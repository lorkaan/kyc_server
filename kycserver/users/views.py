from django.shortcuts import render

# Create your views here.
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import ensure_csrf_cookie
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required


@ensure_csrf_cookie
def csrf(request):
    return JsonResponse({"detail": "CSRF cookie set"})


@require_POST
def login_view(request):
    import json

    data = json.loads(request.body)

    user = authenticate(
        request,
        username=data.get("username"),
        password=data.get("password")
    )

    if user is None:
        return JsonResponse({"error": "Invalid credentials"}, status=400)

    login(request, user)

    return JsonResponse({"success": True})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"success": True})


@login_required
def me(request):
    return JsonResponse({
        "username": request.user.username
    })
