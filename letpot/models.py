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

@dataclass
class LetPotDeviceStatus:
    light_brightness: int
    light_mode: int
    light_schedule_end: tuple[int, int]
    light_schedule_start: tuple[int, int]
    online: int
    plant_days: int
    pump_mode: int
    pump_status: int
    raw: list[int]
    system_on: bool
    system_sound: bool | None
    system_state: int