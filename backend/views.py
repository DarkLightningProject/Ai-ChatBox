import hmac
import os

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def database_check(request):
    expected_token = os.getenv("DATABASE_DIAGNOSTIC_TOKEN")
    supplied_token = request.headers.get("X-Diagnostic-Token", "")
    if not expected_token or not hmac.compare_digest(
        supplied_token.encode("utf-8"),
        expected_token.encode("utf-8"),
    ):
        return JsonResponse({"error": "Not found"}, status=404)

    if connection.vendor != "postgresql":
        return JsonResponse(
            {"error": "Database diagnostic supports PostgreSQL only"},
            status=501,
        )

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT
                current_database(),
                current_user,
                current_schema(),
                current_setting('search_path'),
                to_regclass('public.cache_table'),
                to_regclass('cache_table')
            """
        )
        result = cursor.fetchone()

    return JsonResponse({
        "database": result[0],
        "user": result[1],
        "schema": result[2],
        "search_path": result[3],
        "public_cache_table": result[4],
        "cache_table": result[5],
    })
