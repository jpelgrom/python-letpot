"""Models for Python client for LetPot hydroponic gardens."""

from dataclasses import dataclass
from datetime import time
import time as systime


@dataclass
class AuthenticationInfo:
    """Authentication info model."""

    access_token: str
    access_token_expires: int
    refresh_token: str
    refresh_token_expires: int
    user_id: str
    email: str

    @property
    def is_valid(self) -> bool:
        """Returns if the access token is valid."""
        return self.access_token_expires > int(systime.time())


@dataclass
class LetPotDevice:
    """Device model."""

    serial_number: str
    name: str
    device_type: str
    is_online: bool
    is_remote: bool


@dataclass
class LetPotDeviceStatus:
    """Device status model."""

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
    temperature_unit: int | None = None
    temperature_value: int | None = None
    water_mode: int | None = None
    water_level: int | None = None
