"""Tests for Python client for LetPot hydroponic gardens."""

from letpot.models import AuthenticationInfo

AUTHENTICATION = AuthenticationInfo(
    access_token="access_token",
    access_token_expires=1738368000,  # 2025-02-01 00:00:00 GMT
    refresh_token="refresh_token",
    refresh_token_expires=1740441600,  # 2025-02-25 00:00:00 GMT
    user_id="a1b2c3d4e5f6a1b2c3d4e5f6",
    email="email@example.com",
)
