"""Python client for LetPot hydroponic gardens."""

import time
from aiohttp import ClientSession, ClientResponse

from letpot.exceptions import LetPotAuthenticationException, LetPotConnectionException

from .models import AuthenticationInfo, LetPotDevice


class LetPotClient:
    """Client for connecting to LetPot account."""

    API_HOST = "https://api.letpot.net/app/"

    _session: ClientSession
    _access_token: str | None = None
    _access_token_expires: int = 0
    _refresh_token: str | None = None
    _refresh_token_expires: int = 0
    _user_id: str | None = None
    _email: str | None = None

    def __init__(
        self,
        session: ClientSession | None = None,
        info: AuthenticationInfo | None = None,
    ) -> None:
        self._session = session if session else ClientSession()

        if info is not None:
            self._access_token = info.access_token
            self._access_token_expires = info.access_token_expires
            self._refresh_token = info.refresh_token
            self._refresh_token_expires = info.refresh_token_expires
            self._user_id = info.user_id
            self._email = info.email

    async def _request(self, method: str, path: str) -> ClientResponse:
        """Make a request."""
        if self._access_token is None:
            raise LetPotAuthenticationException("Missing access token, log in first")
        if self._user_id is None:
            raise LetPotAuthenticationException("Missing user id, log in first")

        headers = {"Authorization": self._access_token, "uid": self._user_id}

        return await self._session.request(
            method,
            self.API_HOST + path,
            headers=headers,
        )

    async def login(self, email: str, password: str) -> AuthenticationInfo:
        """Log in and create new authentication info."""
        form = {
            "loginType": "EMAIL",
            "email": email,
            "password": password,
            "refresh_token": "",
        }
        response = await self._session.post(self.API_HOST + "auth/login", data=form)

        if response.status == 403:
            raise LetPotAuthenticationException("Invalid credentials")

        json = await response.json()

        if json["ok"] is not True:
            raise LetPotConnectionException(f"Status not OK: {json["message"]}")

        self._access_token = json["data"]["token"]["token"]
        self._access_token_expires = json["data"]["token"]["exp"]
        self._refresh_token = json["data"]["refreshToken"]["token"]
        self._refresh_token_expires = json["data"]["refreshToken"]["exp"]
        self._user_id = json["data"]["user_id"]
        self._email = email.lower()

        return AuthenticationInfo(
            access_token=self._access_token or "",
            access_token_expires=self._access_token_expires,
            refresh_token=self._refresh_token or "",
            refresh_token_expires=self._refresh_token_expires,
            user_id=self._user_id or "",
            email=self._email,
        )

    async def refresh_token(self) -> AuthenticationInfo:
        """Refresh the current access token."""
        if self._refresh_token is None or self._refresh_token_expires < time.time():
            raise LetPotAuthenticationException("Refresh token is missing or expired")

        headers = {"Rfs-Authorization": self._refresh_token}
        response = await self._session.get(
            self.API_HOST + "auth/refresh", headers=headers
        )

        if response.status == 401:
            raise LetPotAuthenticationException("Invalid refresh token")

        json = await response.json()

        if json["ok"] is not True:
            raise LetPotConnectionException(f"Status not OK: {json["message"]}")

        self._access_token = json["data"]["token"]["token"]
        self._access_token_expires = json["data"]["token"]["exp"]
        self._refresh_token = json["data"]["refreshToken"]["token"]
        self._refresh_token_expires = json["data"]["refreshToken"]["exp"]

        return AuthenticationInfo(
            access_token=self._access_token or "",
            access_token_expires=self._access_token_expires,
            refresh_token=self._refresh_token or "",
            refresh_token_expires=self._refresh_token_expires,
            user_id=self._user_id or "",
            email=self._email or "",
        )

    async def get_devices(self) -> list[LetPotDevice]:
        """Get devices connected to the user."""
        response = await self._request("get", "devices")

        if response.status != 200:
            text = await response.text()

            msg = f"get_devices returned {response.status}: {text}"
            if response.status == 401:
                raise LetPotAuthenticationException(msg)
            else:
                raise LetPotConnectionException(msg)

        json = await response.json()

        devices = []
        for device in json["data"]:
            devices.append(
                LetPotDevice(
                    serial_number=device["sn"],
                    name=device["name"],
                    device_type=device["dev_type"],
                    is_online=device["is_online"],
                    is_remote=device["is_remote"],
                )
            )

        return devices
