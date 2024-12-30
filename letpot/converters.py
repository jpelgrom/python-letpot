"""Python client for LetPot hydrophonic gardens."""

from abc import ABC, abstractmethod
from datetime import time
import math

from letpot.exceptions import LetPotException
from letpot.models import LetPotDeviceStatus


class LetPotDeviceConverter(ABC):
    """Base class for converters and info for device types."""

    @staticmethod
    @abstractmethod
    def supports_type(device_type: str) -> bool:
        """Returns if the converter supports the supplied type."""
        pass

    @staticmethod
    @abstractmethod
    def get_current_status_message() -> list[int]:
        """Returns the message content for getting the current device status."""
        pass

    @staticmethod
    @abstractmethod
    def convert_hex_to_status(hex_message: bytes) -> LetPotDeviceStatus:
        """Converts a hexadecimal bytes status message to a status dataclass."""
        pass

    @staticmethod
    @abstractmethod
    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        """Returns the message content for updating the device status."""
        pass

    @staticmethod
    @abstractmethod
    def get_light_brightness_levels(device_type: str) -> list[int]:
        """Returns the brightness steps supported by the device for this converter."""
        pass

    @staticmethod
    def _hex_bytes_to_int_array(hex_message: bytes) -> list[int]:
        """Converts a hexadecimal bytes message to a list of integers."""
        try:
            decoded_hex = hex_message.decode("utf-8")
            integers = []
            for n in range(0, len(decoded_hex), 2):
                integers.append(int(decoded_hex[n : n + 2], 16))
            return integers
        except Exception as exception:
            raise LetPotException("Unable to convert from hex") from exception


class LPHx1Converter(LetPotDeviceConverter):
    """Converters and info for device type LPH11 (Mini), LPH21 (Air), LPH31 (SE)."""

    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH11", "LPH21", "LPH31"]

    def get_current_status_message() -> list[int]:
        return [97, 1]

    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        return [
            97,
            2,
            1 if status.system_on else 0,
            status.pump_mode,
            status.light_mode,
            math.floor(status.plant_days / 256),
            status.plant_days % 256,
            status.light_schedule_start.hour,
            status.light_schedule_start.minute,
            status.light_schedule_end.hour,
            status.light_schedule_end.minute,
            math.floor(status.light_brightness / 256),
            status.light_brightness % 256,
            1 if status.system_sound is True else 0,
        ]

    def convert_hex_to_status(hex_message: bytes) -> LetPotDeviceStatus | None:
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex_message)
        if data[4] != 98 or data[5] != 1:
            print("Invalid hex message, ignoring")
            return None

        return LetPotDeviceStatus(
            raw=data,
            light_brightness=256 * data[17] + data[18],
            light_mode=data[10],
            light_schedule_end=time(hour=data[15], minute=data[16]),
            light_schedule_start=time(hour=data[13], minute=data[14]),
            online=data[6] == 0,
            plant_days=256 * data[11] + data[12],
            pump_mode=data[9],
            pump_nutrient=None,
            pump_status=data[19],
            system_on=data[8] == 1,
            system_sound=data[20] == 1 if data[20] is not None else None,
            system_state=data[7],
        )

    def get_light_brightness_levels(device_type: str) -> list[int]:
        return [500, 1000] if device_type in ["LPH21", "LPH31"] else []


class IGSorAltConverter(LetPotDeviceConverter):
    """Converters and info for device type IGS01 (Pro), LPH27, LPH37 (SE), LPH39 (Mini)."""

    def supports_type(device_type: str) -> bool:
        return device_type in ["IGS01", "LPH27", "LPH37", "LPH39"]

    def get_current_status_message() -> list[int]:
        return [11, 1]

    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        return [
            11,
            2,
            1 if status.system_on else 0,
            status.pump_mode,
            status.light_mode,
            math.floor(status.plant_days / 256),
            status.plant_days % 256,
            status.light_schedule_start.hour,
            status.light_schedule_start.minute,
            status.light_schedule_end.hour,
            status.light_schedule_end.minute,
            1 if status.system_sound is True else 0,
        ]

    def convert_hex_to_status(hex_message: bytes) -> LetPotDeviceStatus | None:
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex_message)
        if data[4] != 12 or data[5] != 1:
            print("Invalid hex message, ignoring")
            return None

        return LetPotDeviceStatus(
            raw=data,
            light_brightness=None,
            light_mode=data[10],
            light_schedule_end=time(hour=data[15], minute=data[16]),
            light_schedule_start=time(hour=data[13], minute=data[14]),
            online=data[6] == 0,
            plant_days=256 * data[11] + data[12],
            pump_mode=data[9],
            pump_nutrient=None,
            pump_status=None,
            system_on=data[8] == 1,
            system_sound=data[17] == 1 if data[17] is not None else None,
            system_state=data[7],
        )

    def get_light_brightness_levels(device_type: str) -> list[int]:
        return []


class LPH6xConverter(LetPotDeviceConverter):
    """Converters and info for device type LPH60, LPH61, LPH62 (Max)."""

    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH60", "LPH61", "LPH62"]

    def get_current_status_message() -> list[int]:
        return [13, 1]

    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        return [
            13,
            2,
            1 if status.system_on else 0,
            status.pump_mode,
            status.light_mode,
            math.floor(status.plant_days / 256),
            status.plant_days % 256,
            status.light_schedule_start.hour,
            status.light_schedule_start.minute,
            status.light_schedule_end.hour,
            status.light_schedule_end.minute,
            status.water_mode,
            math.floor(status.light_brightness / 256),
            status.light_brightness % 256,
            status.temperature_unit,
            1 if status.system_sound is True else 0,
            1 if status.pump_nutrient is True else 0,
        ]

    def convert_hex_to_status(hex_message: bytes) -> LetPotDeviceStatus | None:
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex_message)
        if data[4] != 14 or data[5] != 1:
            print("Invalid hex message, ignoring")
            return None

        return LetPotDeviceStatus(
            raw=data,
            light_brightness=256 * data[18] + data[19],
            light_mode=data[10],
            light_schedule_end=time(hour=data[15], minute=data[16]),
            light_schedule_start=time(hour=data[13], minute=data[14]),
            online=data[6] == 0,
            plant_days=256 * data[11] + data[12],
            pump_mode=data[9],
            pump_nutrient=data[26] == 1,
            pump_status=None,
            system_on=data[8] == 1,
            system_sound=data[25] == 1 if data[25] is not None else None,
            system_state=data[7],
            temperature_unit=data[24],
            temperature_value=256 * data[22] + data[23],
            water_level=256 * data[20] + data[21],
            water_mode=data[17],
        )

    def get_light_brightness_levels(device_type: str) -> list[int]:
        return [0, 125, 250, 375, 500, 625, 750, 875, 1000]


class LPH63Converter(LetPotDeviceConverter):
    """Converters and info for device type LPH63 (Max)."""

    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH63"]

    def get_current_status_message() -> list[int]:
        return [101, 1]

    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        return [
            101,
            2,
            1 if status.system_on else 0,
            status.pump_mode,
            status.light_mode,
            math.floor(status.plant_days / 256),
            status.plant_days % 256,
            status.light_schedule_start.hour,
            status.light_schedule_start.minute,
            status.light_schedule_end.hour,
            status.light_schedule_end.minute,
            status.water_mode,
            math.floor(status.light_brightness / 256),
            status.light_brightness % 256,
        ]

    def convert_hex_to_status(hex_message: bytes) -> LetPotDeviceStatus | None:
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex_message)
        if data[4] != 102 or data[5] != 1:
            print("Invalid hex message, ignoring")
            return None

        return LetPotDeviceStatus(
            raw=data,
            light_brightness=256 * data[18] + data[19],
            light_mode=data[10],
            light_schedule_end=time(hour=data[15], minute=data[16]),
            light_schedule_start=time(hour=data[13], minute=data[14]),
            online=data[6] == 0,
            plant_days=256 * data[11] + data[12],
            pump_mode=data[9],
            pump_nutrient=None,
            pump_status=data[26],
            system_on=data[8] == 1,
            system_sound=None,
            system_state=data[7],
            temperature_unit=data[24],
            temperature_value=256 * data[22] + data[23],
            water_level=256 * data[20] + data[21],
            water_mode=data[17],
        )

    def get_light_brightness_levels(device_type: str) -> list[int]:
        return [0, 125, 250, 375, 500, 625, 750, 875, 1000]


CONVERTERS: list[LetPotDeviceConverter] = [
    LPHx1Converter,
    IGSorAltConverter,
    LPH6xConverter,
    LPH63Converter,
]
