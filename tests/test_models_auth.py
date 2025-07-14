"""Tests for the AuthenticationInfo model."""

import dataclasses
from datetime import datetime, timedelta

from . import AUTHENTICATION


def test_valid_info() -> None:
    """Test auth with access token expiring in the future is valid."""
    auth_info = dataclasses.replace(
        AUTHENTICATION,
        access_token_expires=int((datetime.now() + timedelta(days=7)).timestamp()),
        refresh_token_expires=int((datetime.now() + timedelta(days=30)).timestamp()),
    )
    assert auth_info.is_valid is True


def test_expired_info() -> None:
    """Test auth with expired access token is considered invalid."""
    auth_info = dataclasses.replace(
        AUTHENTICATION,
        access_token_expires=int((datetime.now() - timedelta(days=7)).timestamp()),
        refresh_token_expires=int((datetime.now() + timedelta(days=14)).timestamp()),
    )
    assert auth_info.is_valid is False
