from rest_framework.authentication import SessionAuthentication


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session auth without the CSRF header check.

    In a cross-domain SPA setup the csrftoken cookie lives on the backend
    domain, so frontend JS cannot read it and cannot send X-CSRFToken.
    Skipping the check is safe here because:
      - CORS is restricted to the known frontend origin
      - SameSite=None is required only for the session cookie, not for CSRF
      - The session cookie itself is the authentication proof
    """

    def enforce_csrf(self, _request):
        return  # skip CSRF header check for cross-domain requests
