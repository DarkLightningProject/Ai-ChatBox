import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email as django_validate_email
from django.db.models import Q
from django.http import JsonResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt

from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from chat.authentication import CsrfExemptSessionAuthentication
from .models import Profile
from .utils import (
    validate_strong_password, rate_limit,
    is_login_locked, record_failed_login, clear_failed_logins,
)

_POST_REQUIRED = "POST required"
_INVALID_JSON = "Invalid JSON"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _send_verification_email(user):
    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    link = f"{FRONTEND_URL}/verify-email/{uid}/{token}"
    send_mail(
        subject="Verify your email",
        message=f"Click the link to verify your email:\n{link}",
        from_email=None,
        recipient_list=[user.email],
    )


@csrf_exempt
@rate_limit("signup", limit=5, window=300)
def signup(request):
    if request.method != "POST":
        return JsonResponse({"error": _POST_REQUIRED}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": _INVALID_JSON}, status=400)

    username = (data.get("username") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not username or not email or not password:
        return JsonResponse({"error": "All fields required"}, status=400)

    if len(username) < 3:
        return JsonResponse({"error": "Username must be at least 3 characters"}, status=400)
    if len(username) > 30:
        return JsonResponse({"error": "Username must be 30 characters or less"}, status=400)

    try:
        django_validate_email(email)
    except ValidationError:
        return JsonResponse({"error": "Invalid email format"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=400)

    if User.objects.filter(email__iexact=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    try:
        validate_strong_password(password)
    except ValidationError as e:
        return JsonResponse({"error": ", ".join(e.messages)}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    try:
        _send_verification_email(user)
    except Exception:
        logger.exception("Failed to send verification email for user %s", user.id)

    return JsonResponse({
        "message": "Signup successful. Please check your email to verify your account.",
        "user_id": user.id
    })


@csrf_exempt
@rate_limit("login", limit=10, window=300)
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"error": _POST_REQUIRED}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": _INVALID_JSON}, status=400)

    identifier = data.get("identifier")  # username OR email
    password = data.get("password")

    if not identifier or not password:
        return JsonResponse({"error": "Credentials required"}, status=400)

    if is_login_locked(identifier):
        return JsonResponse(
            {"error": "Too many failed attempts. Try again in 15 minutes."},
            status=429,
        )

    try:
        user_obj = User.objects.filter(
            Q(username=identifier) | Q(email=identifier)
        ).first()
        if user_obj is None:
            raise User.DoesNotExist
    except User.DoesNotExist:
        record_failed_login(identifier)
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    user = authenticate(username=user_obj.username, password=password)
    if not user:
        record_failed_login(identifier)
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    clear_failed_logins(identifier)
    login(request, user)

    return JsonResponse({
        "message": "Login successful",
        "user_id": user.id,
        "username": user.username,
        "email": user.email
    })


@csrf_exempt
@rate_limit("forgot_password", limit=5, window=300)
def forgot_password(request):
    if request.method != "POST":
        return JsonResponse({"error": _POST_REQUIRED}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": _INVALID_JSON}, status=400)

    email = data.get("email")

    if not email:
        return JsonResponse({"error": "Email required"}, status=400)

    # Always do the same DB lookup regardless of outcome so both paths
    # take the same time — prevents timing-based email enumeration.
    user = User.objects.filter(email=email).first()

    def _send_reset():
        if not user:
            return
        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        reset_link = f"{FRONTEND_URL}/reset-password/{uid}/{token}"
        try:
            send_mail(
                subject="Reset your password",
                message=f"Click the link to reset your password:\n{reset_link}",
                from_email=None,
                recipient_list=[email],
            )
        except Exception:
            logger.exception("Failed to send password reset email for user %s", user.id)

    # Fire-and-forget in a daemon thread so the HTTP response returns at a
    # constant time regardless of whether the email is registered.
    threading.Thread(target=_send_reset, daemon=True).start()

    return JsonResponse({"message": "If that email is registered, a reset link has been sent."})


@api_view(["GET"])
@permission_classes([AllowAny])
def verify_email(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({"error": "Invalid link"}, status=status.HTTP_400_BAD_REQUEST)

    if not default_token_generator.check_token(user, token):
        return Response({"error": "Link expired or invalid"}, status=status.HTTP_400_BAD_REQUEST)

    profile, _ = Profile.objects.get_or_create(user=user)
    if not profile.email_verified:
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])

    return Response({"message": "Email verified successfully"})


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def resend_verification_email(request):
    user = request.user
    profile, _ = Profile.objects.get_or_create(user=user)
    if profile.email_verified:
        return Response({"message": "Email already verified"}, status=status.HTTP_200_OK)
    try:
        _send_verification_email(user)
    except Exception:
        logger.exception("Failed to resend verification email for user %s", user.id)
        return Response({"error": "Failed to send email. Please try again later."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({"message": "Verification email sent"})


def _resolve_active_bans(profile):
    """
    Auto-expires stale FeatureBan rows, then returns a serialisable dict:
    {
      "full_account":           {"expires_at": <iso|null>, "reason": "…"} | null,
      "regular":                … | null,
      "uncensored":             … | null,
      "ocr":                    … | null,
      "multi_debugger":         … | null,
      "multi_debugger_premium": … | null,
    }
    Only features with an *active* ban are included (value != null).
    Expired bans are deleted on the spot.
    """
    from django.utils import timezone as tz
    now    = tz.now()
    result = {}
    to_delete = []

    for ban in profile.feature_bans.all():
        if ban.expires_at and now >= ban.expires_at:
            to_delete.append(ban.pk)
        else:
            result[ban.feature] = {
                "expires_at": ban.expires_at.isoformat() if ban.expires_at else None,
                "reason":     ban.reason or "Violation of terms of service",
            }

    if to_delete:
        from .models import FeatureBan
        FeatureBan.objects.filter(pk__in=to_delete).delete()

    return result


@api_view(["GET"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def me(request):
    get_token(request)  # ensures CSRF cookie is set on every app load
    user = request.user
    try:
        profile    = user.profile
        is_premium = profile.is_premium
        bans       = _resolve_active_bans(profile)
    except Profile.DoesNotExist:
        is_premium = False
        bans       = {}
    return Response({
        "user_id":    user.id,
        "username":   user.username,
        "email":      user.email,
        "is_premium": is_premium,
        "bans":       bans,   # {feature: {expires_at, reason}} — empty {} if no bans
    })


@api_view(["POST"])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response(
        {"message": "Logged out successfully"},
        status=status.HTTP_200_OK
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
def reset_password_api(request):
    uidb64 = request.data.get("uid")
    token = request.data.get("token")
    password = request.data.get("password")

    if not uidb64 or not token or not password:
        return Response(
            {"error": "Invalid request"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response(
            {"error": "Invalid link"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not default_token_generator.check_token(user, token):
        return Response(
            {"error": "Link expired or invalid"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_strong_password(password)
    except ValidationError as e:
        return Response(
            {"error": ", ".join(e.messages)},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.set_password(password)
    user.save()

    return Response({"message": "Password reset successful"})


@api_view(["DELETE"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_account(request):
    user = request.user

    logout(request)
    user.delete()

    return Response(
        {"message": "Account deleted successfully"},
        status=status.HTTP_200_OK
    )


# ─── Profile / Settings endpoints ────────────────────────────────────────────

@api_view(["PUT"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update username."""
    username = (request.data.get("username") or "").strip()
    if not username:
        return Response({"error": "Username is required"}, status=status.HTTP_400_BAD_REQUEST)
    if len(username) < 3:
        return Response({"error": "Username must be at least 3 characters"}, status=status.HTTP_400_BAD_REQUEST)
    if len(username) > 30:
        return Response({"error": "Username must be 30 characters or less"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.exclude(pk=request.user.pk).filter(username=username).exists():
        return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.username = username
    request.user.save(update_fields=["username"])
    return Response({"username": username})


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change password — requires the current password."""
    old_password = request.data.get("old_password", "")
    new_password = request.data.get("new_password", "")

    if not old_password or not new_password:
        return Response({"error": "Both passwords are required"}, status=status.HTTP_400_BAD_REQUEST)
    if not request.user.check_password(old_password):
        return Response({"error": "Current password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
    if old_password == new_password:
        return Response({"error": "New password must differ from the current one"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        validate_strong_password(new_password)
    except ValidationError as e:
        return Response({"error": ", ".join(e.messages)}, status=status.HTTP_400_BAD_REQUEST)

    request.user.set_password(new_password)
    request.user.save()
    login(request, request.user)   # keep the session alive after password change
    return Response({"message": "Password changed successfully"})


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def update_email(request):
    """Update email — requires current password for verification."""
    password  = request.data.get("password", "")
    new_email = (request.data.get("new_email") or "").strip().lower()

    if not password or not new_email:
        return Response({"error": "Password and new email are required"}, status=status.HTTP_400_BAD_REQUEST)
    if not request.user.check_password(password):
        return Response({"error": "Password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        django_validate_email(new_email)
    except ValidationError:
        return Response({"error": "Invalid email format"}, status=status.HTTP_400_BAD_REQUEST)

    if new_email == request.user.email.lower():
        return Response({"error": "New email must differ from your current email"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.exclude(pk=request.user.pk).filter(email__iexact=new_email).exists():
        return Response({"error": "Email already registered to another account"}, status=status.HTTP_400_BAD_REQUEST)

    request.user.email = new_email
    request.user.save(update_fields=["email"])

    # Mark email as unverified and send a new verification link
    try:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        profile.email_verified = False
        profile.save(update_fields=["email_verified"])
        _send_verification_email(request.user)
    except Exception:
        logger.exception("Failed to send verification email after update for user %s", request.user.id)

    return Response({"message": "Email updated. A verification link has been sent to your new address."})
