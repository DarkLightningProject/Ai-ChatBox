from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from backend.middleware import AdminSessionCookieMiddleware


@override_settings(
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    SESSION_COOKIE_NAME="customer_sessionid",
    SESSION_COOKIE_PATH="/api/",
    ADMIN_SESSION_COOKIE_NAME="admin_sessionid",
    ADMIN_SESSION_COOKIE_PATH="/admin/",
)
class AdminSessionCookieMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.customer_cookie = self._encode_session("Robin")
        self.admin_cookie = self._encode_session("master")

    @staticmethod
    def _encode_session(username):
        from django.contrib.sessions.backends.signed_cookies import SessionStore

        session = SessionStore()
        session["username"] = username
        session.save()
        return session.session_key

    def _request(self, path):
        request = self.factory.get(path)
        request.COOKIES = {
            "customer_sessionid": self.customer_cookie,
            "admin_sessionid": self.admin_cookie,
        }
        return request

    def _run_request(self, path):
        seen_user = []

        def view(request):
            seen_user.append(request.session.get("username"))
            request.session["refreshed"] = True
            return HttpResponse("ok")

        handler = AdminSessionCookieMiddleware(SessionMiddleware(view))
        response = handler(self._request(path))
        return seen_user, response

    def test_admin_uses_only_admin_session_cookie(self):
        seen_user, response = self._run_request("/admin/")

        self.assertEqual(seen_user, ["master"])
        self.assertIn("admin_sessionid", response.cookies)
        self.assertNotIn("customer_sessionid", response.cookies)
        self.assertEqual(response.cookies["admin_sessionid"]["path"], "/admin/")

    def test_api_uses_customer_session_cookie(self):
        seen_user, response = self._run_request("/api/auth/me/")

        self.assertEqual(seen_user, ["Robin"])
        self.assertIn("customer_sessionid", response.cookies)
        self.assertNotIn("admin_sessionid", response.cookies)
        self.assertEqual(response.cookies["customer_sessionid"]["path"], "/api/")
