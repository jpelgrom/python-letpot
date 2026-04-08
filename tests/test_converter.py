"""Tests for the converters."""

from freezegun import freeze_time
import pytest

from letpot.converters import (
    CONVERTERS,
    ISEConverter,
    LetPotDeviceConverter,
    LPHx1Converter,
)
from letpot.exceptions import LetPotException

from . import (
    DEVICE_STATUS_DI_CYCLE,
    DEVICE_STATUS_DI_IDLE,
    DEVICE_STATUS_DI_MANUAL,
    DEVICE_STATUS_GARDEN,
)

SUPPORTED_DEVICE_TYPES_GARDEN = [
    "IGS01",
    "LPH11",
    "LPH21",
    "LPH22",
    "LPH27",
    "LPH31",
    "LPH32",
    "LPH37",
    "LPH39",
    "LPH60",
    "LPH61",
    "LPH62",
    "LPH63",
    "LPH64",
]
SUPPORTED_DEVICE_TYPES_WATERING = ["ISE05", "ISE06"]
SUPPORTED_DEVICE_TYPES_ALL = (
    SUPPORTED_DEVICE_TYPES_GARDEN + SUPPORTED_DEVICE_TYPES_WATERING
)


@pytest.mark.parametrize(
    "device_type",
    SUPPORTED_DEVICE_TYPES_ALL,
)
def test_supported_finds_converter(device_type: str) -> None:
    """Test support by a converter for all supported device types."""
    converter = next(
        (conv for conv in CONVERTERS if conv.supports_type(device_type)), None
    )
    assert converter is not None


@pytest.mark.parametrize(
    "device_type",
    SUPPORTED_DEVICE_TYPES_ALL,
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
    ["LPH21", "IGS01", "LPH60", "LPH63", "ISE05"],
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
    assert status == DEVICE_STATUS_GARDEN


def test_ise06_idle_message_to_status() -> None:
    """Test that a message from a ISE06 device type when idle decodes to a certain status."""
    converter = ISEConverter("ISE06")
    message = (
        b"4d000121420100000000000300000000000018000300000000000000000000000000000000"
    )
    status = converter.convert_hex_to_status(message)
    assert status == DEVICE_STATUS_DI_IDLE


@freeze_time("2026-03-01")
def test_ise06_manual_message_to_status() -> None:
    """Test that a message from a ISE06 device type when manually started decodes to a certain status."""
    converter = ISEConverter("ISE06")
    message = (
        b"4d000121420100000101000300000084000018000300000000000200000031000000000000"
    )
    status = converter.convert_hex_to_status(message)
    assert status == DEVICE_STATUS_DI_MANUAL


@freeze_time("2026-03-01")
def test_ise06_cycle_message_to_status() -> None:
    """Test that a message from a ISE06 device type when cycle watering decodes to a certain status."""
    converter = ISEConverter("ISE06")
    message = (
        b"4d00012142010000010100030000007b01000c000501001e000f03000000390000a8840000"
    )
    status = converter.convert_hex_to_status(message)
    assert status == DEVICE_STATUS_DI_CYCLE
