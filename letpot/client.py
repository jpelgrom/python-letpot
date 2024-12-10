from aiohttp import ClientSession, ClientResponse

from .models import AuthenticationInfo, LetPotDevice


class LetPotClient:
    """Client for connecting to LetPot."""

    _session: ClientSession | None = None
    access_token: str | None = None
    access_token_expires: int = 0
    refresh_token: str | None = None
    refresh_token_expires: int = 0
    user_id: str | None = None

    def __init__(self, session: ClientSession | None = None, info: AuthenticationInfo | None = None) -> None:
        self._session = session if session else ClientSession()

        if info is not None:
            self.access_token = info.access_token
            self.access_token_expires = info.access_token_expires
            self.refresh_token = info.refresh_token
            self.refresh_token_expires = info.refresh_token_expires
            self.user_id = info.user_id

    async def _request(self, method: str, path: str, **kwargs) -> ClientResponse:
        """Make a request."""
        headers = {}

        if self.access_token is None:
            raise Exception("Missing access token, log in first")
        else:
            headers["Authorization"] = self.access_token
        
        if self.user_id is None:
            raise Exception("Missing user id, log in first")
        else:
            headers["uid"] = self.user_id

        return await self._session.request(
            method, f"https://api.letpot.net/app/{path}", **kwargs, headers=headers,
        )
    
    async def login(self, email, password) -> AuthenticationInfo:
        """Log in and create new authentication info."""
        form = { 'loginType': 'EMAIL', 'email': email, 'password': password, 'refresh_token': '' }
        response = await self._session.post("https://api.letpot.net/app/auth/login", data=form)

        if response.status == 403:
            raise Exception("Invalid credentials")
        
        json = await response.json()
        
        if json["ok"] != True:
            raise Exception(f"Status not OK: {json["message"]}")
        
        self.access_token = json["data"]["token"]["token"]
        self.access_token_expires = json["data"]["token"]["exp"]
        self.refresh_token = json["data"]["refreshToken"]["token"]
        self.refresh_token_expires = json["data"]["refreshToken"]["exp"]
        self.user_id = json["data"]["user_id"]

        return AuthenticationInfo(
            access_token=self.access_token,
            access_token_expires=self.access_token_expires,
            refresh_token=self.refresh_token,
            refresh_token_expires=self.refresh_token_expires,
            user_id=self.user_id
        )

    async def get_devices(self) -> list[LetPotDevice]:
        """Get devices connected to the user."""
        response = await self._request("get", "devices")

        if response.status != 200:
            text = await response.text()
            raise Exception(f"get_devices returned {response.status}: {text}")
        
        json = await response.json()

        devices = []
        for device in json["data"]:
            devices.append(
                LetPotDevice(
                    serial_number=device["sn"],
                    name=device["name"],
                    type=device["dev_type"],
                    is_online=device["is_online"],
                    is_remote=device["is_remote"]
                )
            )

        return devices