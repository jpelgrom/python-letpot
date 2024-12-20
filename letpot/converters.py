from abc import ABC, abstractmethod


class LetPotDeviceConverter(ABC):
    @staticmethod
    @abstractmethod
    def supports_type(type: str) -> bool:
        """Returns if the converter supports the supplied type."""
        pass

    @staticmethod
    @abstractmethod
    def convert_hex_to_status(self, hex: bytes):
        """Converts a hexadecimal bytes status message to an object."""
        pass

    @staticmethod
    def _hex_bytes_to_int_array(hex: bytes):
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

    def supports_type(type):
        return type in ["LPH21"]

    def convert_hex_to_status(hex: bytes):
        data = LetPotDeviceConverter._hex_bytes_to_int_array(hex)
        if data[4] != 98 or data[5] != 1:
            raise Exception("Invalid hex message")
        
        return {
            "raw": data,
            "is_online": data[6],
            "system": {
                "state": data[7],
                "on": data[8] == 1,
                "sound": { "on": data[20] == 1 } if data[20] is not None else None,
            },
            "pump": {
                "mode": data[9],
                "status": data[19]
            },
            "light": {
                "mode": data[10],
                "schedule": {
                    "start": [data[13], data[14]],
                    "end": [data[15], data[16]]
                },
                "brightness": 256 * data[17] + data[18]
            },
            "plant": {
                "schedule": {
                    "days": 256 * data[11] + data[12]
                }
            }
        }