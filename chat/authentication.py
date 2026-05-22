from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Standard session auth with CSRF enforcement active.
    The bypass has been removed — enforce_csrf() is inherited from
    SessionAuthentication, which validates the X-CSRFToken header on
    every unsafe method (POST / PUT / PATCH / DELETE).
    GET requests are always exempt (Django's CSRFCheck skips safe methods).
    """
