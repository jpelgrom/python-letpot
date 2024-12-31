"""Exceptions for Python client for LetPot hydrophonic gardens."""


class LetPotException(Exception):
    """Generic exception."""


class LetPotConnectionException(LetPotException):
    """LetPot connection exception."""


class LetPotAuthenticationException(LetPotException):
    """LetPot authentication exception."""
