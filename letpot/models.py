from dataclasses import dataclass


@dataclass
class AuthenticationInfo:
    access_token: str
    access_token_expires: int
    refresh_token: str
    refresh_token_expires: int
    user_id: str
    email: str

@dataclass
class LetPotDevice:
    serial_number: str
    name: str
    type: str
    is_online: bool
    is_remote: bool