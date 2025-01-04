"""Python client for LetPot hydroponic gardens."""

from abc import ABC, abstractmethod
from datetime import time
import logging
import math
from typing import Sequence
from aiomqtt.types import PayloadType

from letpot.exceptions import LetPotException
from letpot.models import LetPotDeviceStatus

_LOGGER = logging.getLogger(__name__)

MODEL_AIR = ("LetPot Air", "LPH-AIR")
MODEL_MAX = ("LetPot Max", "LPH-MAX")
MODEL_MINI = ("LetPot Mini", "LPH-MINI")
MODEL_PRO = ("LetPot Pro", "LPH-PRO")
MODEL_SE = ("LetPot Senior", "LPH-SE")


class LetPotDeviceConverter(ABC):
    """Base class for converters and info for device types."""

    _device_type: str

    def __init__(self, device_type: str) -> None:
        """Initialize converter."""
        if not self.supports_type(device_type):
            raise LetPotException("Initializing converter with unsupported device type")
        self._device_type = device_type

    @staticmethod
    @abstractmethod
    def supports_type(device_type: str) -> bool:
        """Returns if the converter supports the supplied type."""
        pass

    @abstractmethod
    def get_device_model(self) -> tuple[str, str] | None:
        """Returns the device model name and code."""

    @abstractmethod
    def get_current_status_message(self) -> list[int]:
        """Returns the message content for getting the current device status."""
        pass

    @abstractmethod
    def convert_hex_to_status(self, message: PayloadType) -> LetPotDeviceStatus | None:
        """Converts a hexadecimal bytes status message to a status dataclass."""
        pass

    @abstractmethod
    def get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
        """Returns the message content for updating the device status."""
        pass

    @abstractmethod
    def get_light_brightness_levels(self) -> list[int]:
        """Returns the brightness steps supported by the device for this converter."""
        pass

    def _hex_bytes_to_int_array(self, hex_message: PayloadType) -> list[int] | None:
        """Converts a hexadecimal bytes message to a list of integers."""
        if not isinstance(hex_message, bytes):
            return None
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

    @staticmethod
    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH11", "LPH21", "LPH31"]

    def get_device_model(self) -> tuple[str, str] | None:
        if self._device_type == "LPH11":
            return MODEL_MINI
        elif self._device_type == "LPH21":
            return MODEL_AIR
        elif self._device_type == "LPH31":
            return MODEL_SE
        else:
            return None

    def get_current_status_message(self) -> list[int]:
        return [97, 1]

    def get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
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
            math.floor(status.light_brightness / 256)
            if status.light_brightness is not None
            else 0,
            status.light_brightness % 256 if status.light_brightness is not None else 0,
            1 if status.system_sound is True else 0,
        ]

    def convert_hex_to_status(self, message: PayloadType) -> LetPotDeviceStatus | None:
        data = self._hex_bytes_to_int_array(message)
        if data is None or data[4] != 98 or data[5] != 1:
            _LOGGER.debug("Invalid message received, ignoring: %s", message)
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

    def get_light_brightness_levels(self) -> list[int]:
        return [500, 1000] if self._device_type in ["LPH21", "LPH31"] else []


class IGSorAltConverter(LetPotDeviceConverter):
    """Converters and info for device type IGS01 (Pro), LPH27, LPH37 (SE), LPH39 (Mini)."""

    @staticmethod
    def supports_type(device_type: str) -> bool:
        return device_type in ["IGS01", "LPH27", "LPH37", "LPH39"]

    def get_device_model(self) -> tuple[str, str] | None:
        if self._device_type == "IGS01":
            return MODEL_PRO
        elif self._device_type in ["LPH27", "LPH37"]:
            return MODEL_SE
        elif self._device_type == "LPH39":
            return MODEL_MINI
        else:
            return None

    def get_current_status_message(self) -> list[int]:
        return [11, 1]

    def get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
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

    def convert_hex_to_status(self, message: PayloadType) -> LetPotDeviceStatus | None:
        data = self._hex_bytes_to_int_array(message)
        if data is None or data[4] != 12 or data[5] != 1:
            _LOGGER.debug("Invalid message received, ignoring: %s", message)
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

    def get_light_brightness_levels(self) -> list[int]:
        return []


class LPH6xConverter(LetPotDeviceConverter):
    """Converters and info for device type LPH60, LPH61, LPH62 (Max)."""

    @staticmethod
    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH60", "LPH61", "LPH62"]

    def get_device_model(self) -> tuple[str, str] | None:
        return MODEL_MAX

    def get_current_status_message(self) -> list[int]:
        return [13, 1]

    def get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
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
            status.water_mode if status.water_mode is not None else 0,
            math.floor(status.light_brightness / 256)
            if status.light_brightness is not None
            else 0,
            status.light_brightness % 256 if status.light_brightness is not None else 0,
            status.temperature_unit if status.temperature_unit is not None else 0,
            1 if status.system_sound is True else 0,
            1 if status.pump_nutrient is True else 0,
        ]

    def convert_hex_to_status(self, message: PayloadType) -> LetPotDeviceStatus | None:
        data = self._hex_bytes_to_int_array(message)
        if data is None or data[4] != 14 or data[5] != 1:
            _LOGGER.debug("Invalid message received, ignoring: %s", message)
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

    def get_light_brightness_levels(self) -> list[int]:
        return [0, 125, 250, 375, 500, 625, 750, 875, 1000]


class LPH63Converter(LetPotDeviceConverter):
    """Converters and info for device type LPH63 (Max)."""

    @staticmethod
    def supports_type(device_type: str) -> bool:
        return device_type in ["LPH63"]

    def get_device_model(self) -> tuple[str, str] | None:
        return MODEL_MAX

    def get_current_status_message(self) -> list[int]:
        return [101, 1]

    def get_update_status_message(self, status: LetPotDeviceStatus) -> list[int]:
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
            status.water_mode if status.water_mode is not None else 0,
            math.floor(status.light_brightness / 256)
            if status.light_brightness is not None
            else 0,
            status.light_brightness % 256 if status.light_brightness is not None else 0,
        ]

    def convert_hex_to_status(self, message: PayloadType) -> LetPotDeviceStatus | None:
        data = self._hex_bytes_to_int_array(message)
        if data is None or data[4] != 102 or data[5] != 1:
            _LOGGER.debug("Invalid message received, ignoring: %s", message)
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

    def get_light_brightness_levels(self) -> list[int]:
        return [0, 125, 250, 375, 500, 625, 750, 875, 1000]


CONVERTERS: Sequence[type[LetPotDeviceConverter]] = [
    LPHx1Converter,
    IGSorAltConverter,
    LPH6xConverter,
    LPH63Converter,
]
