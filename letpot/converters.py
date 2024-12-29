from abc import ABC, abstractmethod
import math

from letpot.models import LetPotDeviceStatus


class LetPotDeviceConverter(ABC):
    @staticmethod
    @abstractmethod
    def supports_type(type: str) -> bool:
        """Returns if the converter supports the supplied type."""
        pass

    @staticmethod
    @abstractmethod
    def get_current_status_message() -> list[int]:
        """Returns the message content for getting the current device status."""
        pass

    @staticmethod
    @abstractmethod
    def convert_hex_to_status(self, hex: bytes) -> LetPotDeviceStatus:
        """Converts a hexadecimal bytes status message to a status dataclass."""
        pass

    @staticmethod
    @abstractmethod
    def get_update_status_message(status: LetPotDeviceStatus) -> list[int]:
        """Returns the message content for updating the device status."""

    @staticmethod
    @abstractmethod
    def get_light_brightness_levels() -> list[int]:
        """Returns the brightness steps supported by the device for this converter."""
        pass

    @staticmethod
    def _hex_bytes_to_int_array(hex: bytes) -> list[int]:
        """Converts a hexadecimal bytes message to a list of integers."""
        try:
            decoded_hex = hex.decode("utf-8")
            integers = []
            for n in range(0, len(decoded_hex), 2):
                integers.append(int(decoded_hex[n:n + 2], 16))
            return integers
        except Exception as e:
            raise Exception(f"Unable to convert from hex: {e}")

class LPH21Converter(LetPotDeviceConverter):
    """Converters and info for device type LPH21."""
    def supports_type(type: str) -> bool:
        return type in ["LPH21"]
    
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
            status.light_schedule_start[0],
            status.light_schedule_start[1],
            status.light_schedule_end[0],
            status.light_schedule_end[1],
            math.floor(status.light_brightness / 256),
            status.light_brightness % 256,
            1 if status.system_sound is True else 0
        ]

    def convert_hex_to_status(hex: bytes) -> LetPotDeviceStatus | None:
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex)
        if data[4] != 98 or data[5] != 1:
            print("Invalid hex message, ignoring")
            return None
        
        return LetPotDeviceStatus(
            raw=data,
            light_brightness=256 * data[17] + data[18],
            light_mode=data[10],
            light_schedule_end=(data[15], data[16]),
            light_schedule_start=(data[13], data[14]),
            online=data[6],
            plant_days=256 * data[11] + data[12],
            pump_mode=data[9],
            pump_status=data[19],
            system_on=data[8] == 1,
            system_sound=data[20] == 1 if data[20] is not None else None,
            system_state=data[7]
        )

    def get_light_brightness_levels() -> list[int]:
        return [500, 1000]