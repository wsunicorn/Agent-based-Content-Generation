"""Small production-only HTTP basic auth guard."""
from __future__ import annotations

import base64
import binascii
import hmac

from django.conf import settings
from django.http import HttpResponse


class BasicAuthMiddleware:
    """Protect the public dashboard/API before a real account system exists."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._is_exempt(request.path):
            return self.get_response(request)

        expected_password = getattr(settings, "APP_BASIC_AUTH_PASSWORD", "")
        if not expected_password:
            return self._challenge("Basic auth password is not configured.")

        header = request.META.get("HTTP_AUTHORIZATION", "")
        if self._is_authorized(header, expected_password):
            return self.get_response(request)

        return self._challenge("Authentication required.")

    @staticmethod
    def _is_exempt(path: str) -> bool:
        for prefix in getattr(settings, "APP_BASIC_AUTH_EXEMPT_PATHS", []):
            if path.startswith(prefix):
                return True
        return False

    @staticmethod
    def _is_authorized(header: str, expected_password: str) -> bool:
        if not header.lower().startswith("basic "):
            return False
        try:
            raw = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
            username, password = raw.split(":", 1)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return False

        expected_username = getattr(settings, "APP_BASIC_AUTH_USERNAME", "admin")
        return hmac.compare_digest(username, expected_username) and hmac.compare_digest(
            password,
            expected_password,
        )

    @staticmethod
    def _challenge(message: str) -> HttpResponse:
        response = HttpResponse(message, status=401)
        response["WWW-Authenticate"] = 'Basic realm="Content Pipeline"'
        return response
