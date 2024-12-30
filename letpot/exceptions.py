"""Exceptions for Python client for LetPot hydrophonic gardens."""


class LetPotException(Exception):
    """Generic exception."""


class LetPotConnectionException(Exception):
    """LetPot connection exception."""


class LetPotAuthenticationException(Exception):
    """LetPot authentication exception."""
