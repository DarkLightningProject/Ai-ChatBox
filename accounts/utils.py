import re
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import JsonResponse


def _get_client_ip(request):
    """
    Return the real client IP safely.

    If SECURE_PROXY_SSL_HEADER is configured (production behind a reverse proxy
    such as Render / Heroku), trust X-Forwarded-For but take the RIGHTMOST entry
    — that entry is appended by our own trusted proxy and cannot be forged by
    the client (unlike the leftmost entry which the client controls).

    In local development (no proxy header configured), fall back to REMOTE_ADDR.
    """
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded_for:
            return forwarded_for.strip().split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def rate_limit(key_prefix, limit, window):
    """
    IP-based rate limiter using atomic cache operations.
    limit = max requests allowed in `window` seconds.

    Uses cache.add() + cache.incr() which are atomic in all Django cache
    backends (Redis, Memcached, DatabaseCache) — no race condition.

    Skipped entirely when DEBUG=True so local testing with multiple users
    is not blocked by shared 127.0.0.1 IP.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if settings.DEBUG:
                return view_func(request, *args, **kwargs)

            ip        = _get_client_ip(request)
            cache_key = f"rl:{key_prefix}:{ip}"

            # cache.add is atomic — only sets if key is absent
            cache.add(cache_key, 0, timeout=window)
            try:
                count = cache.incr(cache_key)
            except ValueError:
                # Key disappeared between add and incr (very rare) — reset it
                cache.set(cache_key, 1, timeout=window)
                count = 1

            if count > limit:
                return JsonResponse(
                    {"error": "Too many requests. Please try again later."},
                    status=429,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ─── Login lockout helpers ────────────────────────────────────────────────────

_LOGIN_FAIL_LIMIT  = 10    # max failures before lockout
_LOGIN_FAIL_WINDOW = 900   # 15 minutes


def is_login_locked(identifier: str) -> bool:
    """Return True if this identifier has hit the failed-login threshold."""
    count = cache.get(f"login_fail:{identifier.lower()}", 0)
    return count >= _LOGIN_FAIL_LIMIT


def record_failed_login(identifier: str) -> int:
    """Increment the per-identifier failed-login counter. Returns new count."""
    key = f"login_fail:{identifier.lower()}"
    cache.add(key, 0, timeout=_LOGIN_FAIL_WINDOW)
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=_LOGIN_FAIL_WINDOW)
        return 1


def clear_failed_logins(identifier: str) -> None:
    """Clear the failed-login counter after a successful login."""
    cache.delete(f"login_fail:{identifier.lower()}")


# ─── Password validation ──────────────────────────────────────────────────────

def validate_strong_password(password):
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one number.")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise ValidationError("Password must contain at least one special character.")
