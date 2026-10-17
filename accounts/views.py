import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import (
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    User,
    username_validator,
)

GENERIC_LOGIN_ERROR = "Kullanıcı adı / e-posta veya parola hatalı."


# --- Helpers -------------------------------------------------------------


def _errors(errors, status=400):
    return JsonResponse({"errors": errors}, status=status)


def _read_json(request):
    """Return the parsed JSON object body, or None when it is invalid."""
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _text(data, key):
    value = data.get(key, "")
    return value if isinstance(value, str) else ""


def _validation_messages(exc):
    return list(exc.messages)


# --- Pages ---------------------------------------------------------------


def _safe_next(request):
    target = request.GET.get("next", "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return "/"


@ensure_csrf_cookie
def login_page(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    return render(request, "login.html")


@ensure_csrf_cookie
def register_page(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))
    return render(request, "register.html")


# --- API -----------------------------------------------------------------


@require_POST
def register(request):
    data = _read_json(request)
    if data is None:
        return _errors({"__all__": ["Geçersiz istek."]})

    username = _text(data, "username").strip()
    email = _text(data, "email").strip()
    password = _text(data, "password")
    errors = {}

    if len(username) < USERNAME_MIN_LENGTH or len(username) > USERNAME_MAX_LENGTH:
        errors["username"] = [
            f"Kullanıcı adı {USERNAME_MIN_LENGTH}-{USERNAME_MAX_LENGTH} karakter olmalı."
        ]
    else:
        try:
            username_validator(username)
        except ValidationError as exc:
            errors["username"] = _validation_messages(exc)
        else:
            if User.objects.filter(username__iexact=username).exists():
                errors["username"] = ["Bu kullanıcı adı zaten alınmış."]

    if not email:
        errors["email"] = ["E-posta adresi gerekli."]
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors["email"] = ["Geçerli bir e-posta adresi gir."]
        else:
            if User.objects.filter(email__iexact=email).exists():
                errors["email"] = ["Bu e-posta adresi zaten kayıtlı."]

    if not password:
        errors["password"] = ["Parola gerekli."]
    else:
        try:
            validate_password(password, user=User(username=username, email=email))
        except ValidationError as exc:
            errors["password"] = _validation_messages(exc)

    if errors:
        return _errors(errors)

    try:
        user = User.objects.create_user(username=username, email=email, password=password)
    except IntegrityError:
        # Lost a race against a concurrent registration with the same values.
        return _errors({"__all__": ["Bu kullanıcı adı veya e-posta zaten kayıtlı."]})

    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.username}, status=201)


@require_POST
def login_view(request):
    data = _read_json(request)
    if data is None:
        return _errors({"__all__": ["Geçersiz istek."]})

    identifier = _text(data, "identifier").strip()
    password = _text(data, "password")
    if not identifier or not password:
        return _errors({"__all__": ["Kullanıcı adı / e-posta ve parola gerekli."]})

    lookup = "email__iexact" if "@" in identifier else "username__iexact"
    found = User.objects.filter(**{lookup: identifier}).first()
    # authenticate() also runs the password hasher for unknown users, keeping
    # response timing similar whether or not the account exists.
    user = authenticate(
        request,
        username=found.username if found else identifier,
        password=password,
    )
    if user is None:
        return _errors({"__all__": [GENERIC_LOGIN_ERROR]}, status=401)

    login(request, user)
    return JsonResponse({"authenticated": True, "username": user.username})


@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({"authenticated": False, "username": None})


@require_GET
@ensure_csrf_cookie
def me(request):
    if request.user.is_authenticated:
        return JsonResponse({"authenticated": True, "username": request.user.username})
    return JsonResponse({"authenticated": False, "username": None})
