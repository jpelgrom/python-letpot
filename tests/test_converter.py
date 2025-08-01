"""Tests for the converters."""

from datetime import time

import pytest

from letpot.converters import CONVERTERS, LPHx1Converter, LetPotDeviceConverter
from letpot.exceptions import LetPotException
from letpot.models import LetPotDeviceErrors, LetPotDeviceStatus, LightMode


SUPPORTED_DEVICE_TYPES = [
    "IGS01",
    "LPH11",
    "LPH21",
    "LPH27",
    "LPH31",
    "LPH37",
    "LPH39",
    "LPH60",
    "LPH61",
    "LPH62",
    "LPH63",
]
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


@pytest.mark.parametrize(
    "device_type",
    SUPPORTED_DEVICE_TYPES,
)
def test_supported_finds_converter(device_type: str) -> None:
    """Test support by a converter for all supported device types."""
    converter = next(
        (conv for conv in CONVERTERS if conv.supports_type(device_type)), None
    )
    assert converter is not None


@pytest.mark.parametrize(
    "device_type",
    SUPPORTED_DEVICE_TYPES,
)
def test_supported_has_model(device_type: str) -> None:
    """Test model information for all supported device types."""
    converter = next(conv for conv in CONVERTERS if conv.supports_type(device_type))(
        device_type
    )
    model_info = converter.get_device_model()
    assert model_info is not None


def test_unsupported_finds_no_converter() -> None:
    """Test that no converter reports support for an unknown device type."""
    converter = next((conv for conv in CONVERTERS if conv.supports_type("TEST1")), None)
    assert converter is None


@pytest.mark.parametrize(
    "converter",
    CONVERTERS,
)
def test_unsupported_raises_exception(converter: type[LetPotDeviceConverter]) -> None:
    """Test that creating a converter for an unknown device type isn't possible."""
    with pytest.raises(LetPotException, match="unsupported device type"):
        converter("TEST1")


@pytest.mark.parametrize(
    "device_type",
    ["LPH21", "IGS01", "LPH60", "LPH63"],
)
def test_unexpected_status_is_ignored(device_type: str) -> None:
    """Test that processing a weird status message returns None."""
    converter = next(conv for conv in CONVERTERS if conv.supports_type(device_type))(
        device_type
    )

    different_type_message = "string"
    status = converter.convert_hex_to_status(different_type_message)
    assert status is None

    unexpected_message = b"4d0001090203142f2901007d03"
    status2 = converter.convert_hex_to_status(unexpected_message)
    assert status2 is None


def test_lph21_message_to_status() -> None:
    """Test that a message from a LPH21 device type decodes to a certain status."""
    converter = LPHx1Converter("LPH21")
    message = b"4d000112620100010101010000071e110001f4000000"
    status = converter.convert_hex_to_status(message)
    assert status == DEVICE_STATUS
