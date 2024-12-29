from dataclasses import dataclass
from datetime import time


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
    light_brightness: int | None
    light_mode: int
    light_schedule_end: time
    light_schedule_start: time
    online: bool
    plant_days: int
    pump_mode: int
    pump_nutrient: int | None
    pump_status: int | None
    raw: list[int]
    system_on: bool
    system_sound: bool | None
    system_state: int
    temperature_unit: int | None
    temperature_value: int | None
    water_mode: int | None
    water_level: int | None