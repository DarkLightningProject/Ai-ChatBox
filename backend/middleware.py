from django.conf import settings


class AdminSessionCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_admin_request(request.path_info):
            request.COOKIES = request.COOKIES.copy()
            admin_cookie = request.COOKIES.pop(
                settings.ADMIN_SESSION_COOKIE_NAME, None
            )
            if admin_cookie:
                request.COOKIES[settings.SESSION_COOKIE_NAME] = admin_cookie
            else:
                request.COOKIES.pop(settings.SESSION_COOKIE_NAME, None)

        response = self.get_response(request)

        if self._is_admin_request(request.path_info):
            session_cookie = response.cookies.pop(
                settings.SESSION_COOKIE_NAME, None
            )
            if session_cookie:
                response.cookies[settings.ADMIN_SESSION_COOKIE_NAME] = (
                    session_cookie.value
                )
                admin_cookie = response.cookies[
                    settings.ADMIN_SESSION_COOKIE_NAME
                ]
                for key, value in session_cookie.items():
                    if value:
                        admin_cookie[key] = value
                admin_cookie["path"] = settings.ADMIN_SESSION_COOKIE_PATH

        return response

    @staticmethod
    def _is_admin_request(path):
        return path == "/admin" or path.startswith("/admin/")
