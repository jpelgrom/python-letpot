"""Tests for Python client for LetPot hydroponic gardens."""

from datetime import time
from letpot.models import (
    AuthenticationInfo,
    LetPotDeviceErrors,
    LetPotDeviceStatus,
    LightMode,
)

AUTHENTICATION = AuthenticationInfo(
    access_token="access_token",
    access_token_expires=1738368000,  # 2025-02-01 00:00:00 GMT
    refresh_token="refresh_token",
    refresh_token_expires=1740441600,  # 2025-02-25 00:00:00 GMT
    user_id="a1b2c3d4e5f6a1b2c3d4e5f6",
    email="email@example.com",
)


DEVICE_STATUS = LetPotDeviceStatus(
    errors=LetPotDeviceErrors(low_water=True),
    light_brightness=500,
    light_mode=LightMode.VEGETABLE,
    light_schedule_end=time(17, 0),
    light_schedule_start=time(7, 30),
    online=True,
    plant_days=0,
    pump_mode=1,
    pump_nutrient=None,
    pump_status=0,
    raw=[77, 0, 1, 18, 98, 1, 0, 1, 1, 1, 1, 0, 0, 7, 30, 17, 0, 1, 244, 0, 0, 0],
    system_on=True,
    system_sound=False,
    temperature_unit=None,
    temperature_value=None,
    water_mode=None,
    water_level=None,
)
