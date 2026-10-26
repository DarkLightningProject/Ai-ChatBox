from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings


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
