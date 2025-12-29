from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate,login
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.db.models import Q
import json
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.shortcuts import render, redirect
from django.http import HttpResponse
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from .utils import validate_strong_password
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.core.exceptions import ValidationError
from chat.authentication import CsrfExemptSessionAuthentication
from django.conf import settings


from django.contrib.auth import logout
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import os

from chat.authentication import CsrfExemptSessionAuthentication

# Create your views here.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
@csrf_exempt
def signup(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if not username or not email or not password:
        return JsonResponse({"error": "All fields required"}, status=400)

    if User.objects.filter(username=username).exists():
        return JsonResponse({"error": "Username already taken"}, status=400)

    if User.objects.filter(email=email).exists():
        return JsonResponse({"error": "Email already registered"}, status=400)

    # 🔐 STRONG PASSWORD CHECK (IMPORTANT)
    try:
        validate_strong_password(password)
    except ValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    user = User.objects.create_user(
        username=username,
        email=email,
        password=password
    )

    return JsonResponse({
        "message": "Signup successful",
        "user_id": user.id
    })

@csrf_exempt
def login_view(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    identifier = data.get("identifier")  # username OR email
    password = data.get("password")

    if not identifier or not password:
        return JsonResponse({"error": "Credentials required"}, status=400)

    try:
        user_obj = User.objects.get(
            Q(username=identifier) | Q(email=identifier)
        )
    except User.DoesNotExist:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    user = authenticate(username=user_obj.username, password=password)
    if not user:
        return JsonResponse({"error": "Invalid credentials"}, status=401)

    # 🔥 THIS IS THE MISSING LINE (CRITICAL)
    login(request, user)

    return JsonResponse({
        "message": "Login successful",
        "user_id": user.id,
        "username": user.username,
        "email": user.email
    })

@csrf_exempt
def forgot_password(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    data = json.loads(request.body)
    email = data.get("email")

    if not email:
        return JsonResponse({"error": "Email required"}, status=400)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return JsonResponse({"error": "Email not found"}, status=404)

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    domain = get_current_site(request).domain

    reset_link = f"{FRONTEND_URL}/reset-password/{uid}/{token}"



    send_mail(
        subject="Reset your password",
        message=f"Click the link to reset your password:\n{reset_link}",
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        recipient_list=[email],
    )

    return JsonResponse({"message": "Password reset email sent"})


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([IsAuthenticated])
def logout_view(request):
    logout(request)  # 🔥 clears session
    return Response(
        {"message": "Logged out successfully"},
        status=status.HTTP_200_OK
    )


@api_view(["POST"])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])   # ✅ PUBLIC ENDPOINT

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

    # 🔐 STRONG PASSWORD CHECK (CRITICAL)
    try:
        validate_strong_password(password)
    except ValidationError as e:
        return Response(
            {"error": str(e)},
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

    # logout first (clears session)
    logout(request)

    # delete user (CASCADE deletes related objects)
    user.delete()

    return Response(
        {"message": "Account deleted successfully"},
        status=status.HTTP_200_OK
    )