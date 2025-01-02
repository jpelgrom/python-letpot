"""Tests for the AuthenticationInfo model."""

import dataclasses
from datetime import datetime, timedelta

from letpot.models import AuthenticationInfo

INFO = AuthenticationInfo(
    access_token="abcdef",
    access_token_expires=0,
    refresh_token="123456",
    refresh_token_expires=0,
    user_id="a1b2c3d4e5f6a1b2c3d4e5f6",
    email="email@example.com",
)


def test_valid_info() -> None:
    """Test auth with access token expiring in the future is valid."""
    auth_info = dataclasses.replace(
        INFO,
        access_token_expires=int((datetime.now() + timedelta(days=7)).timestamp()),
        refresh_token_expires=int((datetime.now() + timedelta(days=30)).timestamp()),
    )
    assert auth_info.is_valid is True


def test_expired_info() -> None:
    """Test auth with expired access token is considered invalid."""
    auth_info = dataclasses.replace(
        INFO,
        access_token_expires=int((datetime.now() - timedelta(days=7)).timestamp()),
        refresh_token_expires=int((datetime.now() + timedelta(days=14)).timestamp()),
    )
    assert auth_info.is_valid is False
