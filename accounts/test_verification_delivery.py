from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import Profile


@override_settings(
    DEBUG=True,
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "verification-delivery-tests",
        }
    },
)
class VerificationEmailDeliveryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_verified_user_can_log_in_with_case_insensitive_email(self):
        user = User.objects.create_user(
            username="verified-user",
            email="verified@example.com",
            password="StrongPass1!",
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        verify_response = self.client.get(
            f"/api/auth/verify-email/{uid}/{token}/"
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(Profile.objects.get(user=user).email_verified)

        login_response = self.client.post(
            "/api/auth/login/",
            data={
                "identifier": "Verified@Example.com",
                "password": "StrongPass1!",
            },
            content_type="application/json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["message"], "Login successful")

    def test_signup_reports_failure_and_second_delivery_failure_only_shows_notice(self):
        with patch("accounts.views._send_verification_email", side_effect=OSError("mail unavailable")):
            signup_response = self.client.post(
                "/api/auth/signup/",
                data={
                    "username": "prototype-user",
                    "email": "prototype@example.com",
                    "password": "StrongPass1!",
                },
                content_type="application/json",
            )

        self.assertEqual(signup_response.status_code, 200)
        self.assertFalse(signup_response.json()["verification_email_sent"])

        user = User.objects.get(username="prototype-user")
        self.client.force_login(user)
        with patch("accounts.views._send_verification_email", side_effect=OSError("mail unavailable")):
            resend_response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(resend_response.status_code, 500)
        self.assertIn("failed more than once", resend_response.json()["error"])
        self.assertIn("try again later", resend_response.json()["error"])

        with patch("accounts.views._send_verification_email") as send_email:
            retry_response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(retry_response.status_code, 200)
        send_email.assert_called_once()

    def test_successful_resend_clears_failure_counter(self):
        user = User.objects.create_user(
            username="resend-user",
            email="resend@example.com",
            password="StrongPass1!",
        )
        cache.set(f"verification_email_failures:{user.pk}", 1)
        self.client.force_login(user)

        with patch("accounts.views._send_verification_email"):
            response = self.client.post("/api/auth/resend-verification/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(cache.get(f"verification_email_failures:{user.pk}"))
