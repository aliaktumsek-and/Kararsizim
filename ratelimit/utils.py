"""Database-backed sliding-window rate limiting.

Serverless functions share no memory, so counters live in the database. Only a
keyed hash of the limited value is stored (see RateLimitHit), never the raw IP.
"""

import hashlib
import hmac
import math
import random
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

from .models import RateLimitHit

PRUNE_AFTER = timedelta(days=1)
PRUNE_PROBABILITY = 0.02


@dataclass(frozen=True)
class Rule:
    scope: str
    limit: int
    window: int  # seconds


# Anti-bot limits, generous enough for a classroom sharing one network.
LOGIN_IP = Rule("login-ip", 20, 15 * 60)  # every login attempt from one IP
LOGIN_FAILS = Rule("login-fail", 5, 15 * 60)  # failed attempts for one account
REGISTER_IP = Rule("register-ip", 60, 60 * 60)
POLL_CREATE = (Rule("poll-hour", 5, 60 * 60), Rule("poll-day", 20, 24 * 60 * 60))
VOTE_ANON = (Rule("vote-anon-min", 10, 60), Rule("vote-anon-hour", 120, 60 * 60))
VOTE_MEMBER = (Rule("vote-member-min", 30, 60),)


def client_ip(request):
    """The caller's IP. Forwarded headers are trusted only behind a known proxy (Vercel)."""
    if getattr(settings, "TRUST_PROXY_HEADERS", False):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.META.get("REMOTE_ADDR", "") or "unknown"


def _hash(rule, key):
    secret = settings.SECRET_KEY.encode()
    return hmac.new(secret, f"{rule.scope}|{key}".encode(), hashlib.sha256).hexdigest()


def _recent(rule, key, now):
    since = now - timedelta(seconds=rule.window)
    return RateLimitHit.objects.filter(scope=rule.scope, key_hash=_hash(rule, key), created_at__gt=since)


def retry_after(rule, key):
    """Seconds to wait before `key` may act again under `rule`; 0 when allowed."""
    now = timezone.now()
    hits = list(_recent(rule, key, now).order_by("created_at").values_list("created_at", flat=True)[: rule.limit])
    if len(hits) < rule.limit:
        return 0
    wait = (hits[0] + timedelta(seconds=rule.window) - now).total_seconds()
    return max(1, math.ceil(wait))


def record(rule, key):
    now = timezone.now()
    RateLimitHit.objects.create(scope=rule.scope, key_hash=_hash(rule, key), created_at=now)
    if random.random() < PRUNE_PROBABILITY:
        RateLimitHit.objects.filter(created_at__lt=now - PRUNE_AFTER).delete()


def clear(rule, key):
    RateLimitHit.objects.filter(scope=rule.scope, key_hash=_hash(rule, key)).delete()


def hit(rules, key):
    """Count one action against every rule. Returns 0 when allowed, or the seconds to wait.

    Nothing is recorded for a blocked action, so retrying early never extends the wait.
    """
    if isinstance(rules, Rule):
        rules = (rules,)
    wait = max((retry_after(rule, key) for rule in rules), default=0)
    if wait:
        return wait
    for rule in rules:
        record(rule, key)
    return 0


def _duration(seconds):
    if seconds < 60:
        return f"{seconds} saniye"
    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        return f"{minutes} dakika"
    return f"{math.ceil(minutes / 60)} saat"


def too_many(seconds):
    response = JsonResponse(
        {"errors": {"__all__": [f"Çok fazla deneme yaptın. {_duration(seconds)} sonra tekrar dene."]}},
        status=429,
    )
    response["Retry-After"] = str(seconds)
    return response
