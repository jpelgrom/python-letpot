"""Python client for LetPot hydroponic gardens."""

import asyncio
import dataclasses
import logging
import os
import ssl
import time as systime
from collections.abc import Coroutine
from datetime import time
from functools import wraps
from hashlib import md5, sha256
from typing import Any, Callable, ParamSpec, TypeVar, cast

import aiomqtt

from letpot.converters import CONVERTERS, LetPotDeviceConverter
from letpot.exceptions import (
    LetPotAuthenticationException,
    LetPotConnectionException,
    LetPotException,
    LetPotFeatureException,
)
from letpot.models import (
    AuthenticationInfo,
    DeviceFeature,
    LetPotDeviceInfo,
    LetPotDeviceStatus,
    LightMode,
    TemperatureUnit,
)

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound="LetPotDeviceClient")
_R = TypeVar("_R")
P = ParamSpec("P")


def requires_feature(
    *required_feature: DeviceFeature,
) -> Callable[
    [Callable[P, Coroutine[Any, Any, _R]]],
    Callable[P, Coroutine[Any, Any, _R]],
]:
    """Decorate the function to require device type support for a specific feature (inferred from serial)."""

    def decorator(
        func: Callable[P, Coroutine[Any, Any, _R]],
    ) -> Callable[P, Coroutine[Any, Any, _R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> _R:
            self = cast(LetPotDeviceClient, args[0])
            serial = cast(str, args[1])
            exception_message = f"Device missing required feature: {required_feature}"
            try:
                supported_features = self._converter(serial).supported_features()
                if not any(
                    feature in supported_features for feature in required_feature
                ):
                    raise LetPotFeatureException(exception_message)
            except LetPotException:
                raise LetPotFeatureException(exception_message)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def _create_ssl_context() -> ssl.SSLContext:
    """Create a SSL context for the MQTT connection, avoids a blocking call later."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    return context


_SSL_CONTEXT = _create_ssl_context()


class LetPotDeviceClient:
    """Client for connecting to LetPot device."""

    AUTH_ERROR_RC = [4, 5, 134, 135]
    BROKER_HOST = "broker.letpot.net"
    MTU = 128

    _client: aiomqtt.Client | None = None
    _client_task: asyncio.Task | None = None
    _connected: asyncio.Future[bool] | None = None
    _topics: list[str] = []
    _message_id: int = 0

    _user_id: str
    _email: str

    _device_callbacks: dict[str, Callable[[LetPotDeviceStatus], None]] = {}
    _device_status_last: dict[str, LetPotDeviceStatus | None] = {}
    _device_status_pending: dict[str, LetPotDeviceStatus | None] = {}
    _device_status_timeout: dict[str, asyncio.Task | None] = {}
    _device_status_event: dict[str, asyncio.Event | None] = {}

    def __init__(self, info: AuthenticationInfo) -> None:
        self._user_id = info.user_id
        self._email = info.email

    def _converter(self, serial: str) -> LetPotDeviceConverter:
        """Get the device converter for the current serial number."""
        device_type = serial[:5]
        for converter in CONVERTERS:
            if converter.supports_type(device_type):
                return converter(device_type)
        raise LetPotException("No converter available for device type")

    # region MQTT internals

    def _generate_client_id(self) -> str:
        """Generate a client identifier for the connection."""
        return f"LetPot_{round(systime.time() * 1000)}_{os.urandom(4).hex()[:8]}"

    def _generate_message_packets(
        self, maintype: int, subtype: int, message: list[int]
    ) -> list[str]:
        """Convert a message to one or more packets with the message payload."""
        length = len(message)
        max_packet_size = self.MTU - 6
        num_packets = (length + max_packet_size - 1) // max_packet_size

        packets = []
        for n in range(num_packets):
            start = n * max_packet_size
            end = min(start + max_packet_size, length)
            payload = message[start:end]

            if n < num_packets - 1:
                packet = [
                    (subtype << 2) | maintype,
                    16,
                    self._message_id,
                    len(payload) + 4,
                    length % 256,
                    length // 256,
                    *payload,
                ]
            else:
                packet = [
                    (subtype << 2) | maintype,
                    0,
                    self._message_id,
                    len(payload),
                    *payload,
                ]

            packets.append("".join(f"{byte:02x}" for byte in packet))
            self._message_id += 1

        return packets

    def _handle_message(self, message: aiomqtt.Message) -> None:
        """Process incoming messages from the broker."""
        try:
            serial = message.topic.value.split("/")[0]
            status = self._converter(serial).convert_hex_to_status(message.payload)

            if status is not None:
                self._device_status_pending[serial] = None
                self._device_status_last[serial] = status
                if (callback := self._device_callbacks.get(serial)) is not None:
                    callback(status)
                event = self._device_status_event.get(serial)
                if event is not None and not event.is_set():
                    event.set()
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                f"Exception while handling message for {message.topic.value}, ignoring",
                exc_info=True,
            )

    async def _publish(self, serial: str, message: list[int]) -> None:
        """Publish a message to the device command topic."""
        if self._client is None:
            raise LetPotException("Missing client to publish message with")

        messages = self._generate_message_packets(
            1, 19, message
        )  # maintype 1: data, subtype 19: custom
        topic = f"{serial}/cmd"
        try:
            for publish_message in messages:
                await self._client.publish(topic, payload=publish_message)
        except aiomqtt.MqttError as err:
            if isinstance(err, aiomqtt.MqttCodeError) and err.rc in self.AUTH_ERROR_RC:
                msg = "Publishing failed due to authentication error"
                _LOGGER.error("%s: %s", msg, err)
                raise LetPotAuthenticationException(msg) from err
            else:
                msg = "Publishing failed with unexpected error"
                raise LetPotConnectionException(msg) from err

    def _get_publish_status(self, serial: str) -> LetPotDeviceStatus:
        """Get the device status for publishing (pending update or latest)."""
        if (status := self._device_status_pending.get(serial)) is not None:
            return status
        if (status := self._device_status_last.get(serial)) is not None:
            return status
        raise LetPotException("Client doesn't have a status for publishing")

    async def _clear_pending_status(self, serial: str) -> None:
        """Clear the pending status after a timeout, to prevent an out of date status."""
        await asyncio.sleep(5)
        self._device_status_pending[serial] = None
        self._device_status_timeout[serial] = None

    async def _publish_status(self, serial: str, status: LetPotDeviceStatus) -> None:
        """Set the device status."""
        if self._client is None:
            raise LetPotException("Missing converter/client to publish message with")

        if (task := self._device_status_timeout.get(serial)) is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._device_status_pending[serial] = status
        self._device_status_timeout[serial] = asyncio.get_event_loop().create_task(
            self._clear_pending_status(serial)
        )
        await self._publish(
            serial, self._converter(serial).get_update_status_message(status)
        )

    async def _connect(self) -> None:
        """Connect to the broker for device communication."""
        username = f"{self._email}__letpot_v3"
        password = sha256(
            f"{self._user_id}|{md5(username.encode()).hexdigest()}".encode()
        ).hexdigest()
        connection_attempts = 0
        while True:
            try:
                _LOGGER.debug("Connecting to MQTT broker")
                async with aiomqtt.Client(
                    hostname=self.BROKER_HOST,
                    port=443,
                    username=username,
                    password=password,
                    identifier=self._generate_client_id(),
                    protocol=aiomqtt.ProtocolVersion.V5,
                    transport="websockets",
                    tls_context=_SSL_CONTEXT,
                    tls_insecure=False,
                    websocket_path="/mqttwss",
                ) as client:
                    if connection_attempts >= 1:
                        _LOGGER.info("Reconnected to MQTT broker")

                    self._client = client
                    self._message_id = 0
                    connection_attempts = 0

                    # Restore active subscriptions
                    for topic in self._topics:
                        _LOGGER.debug(f"Restoring subscription to {topic}")
                        await client.subscribe(topic)

                    if self._connected is not None and not self._connected.done():
                        self._connected.set_result(True)

                    async for message in client.messages:
                        self._handle_message(message)
            except aiomqtt.MqttError as err:
                self._client = None

                if isinstance(err, aiomqtt.MqttCodeError):
                    if err.rc in self.AUTH_ERROR_RC:
                        msg = "MQTT auth error"
                        _LOGGER.error("%s: %s", msg, err)
                        auth_exception = LetPotAuthenticationException(msg)
                        if self._connected is not None and not self._connected.done():
                            self._connected.set_exception(auth_exception)
                        raise auth_exception from err

                connection_attempts += 1
                if connection_attempts == 1:
                    _LOGGER.info("MQTT connection error, reconnecting...: %s", err)
                else:
                    reconnect_interval = min((connection_attempts - 1) * 15, 600)
                    _LOGGER.debug(
                        "MQTT connection error, retrying in %i seconds: %s",
                        reconnect_interval,
                        err,
                    )
                    await asyncio.sleep(reconnect_interval)
            finally:
                self._client = None
                if self._connected is not None:
                    if not self._connected.done():
                        self._connected.set_result(False)
                    elif (
                        self._connected.exception() is None
                    ):  # Shutdown because task ended
                        self._connected = None

    async def _disconnect(self) -> None:
        """Cancels the active device client connection, if any."""
        if self._client_task is not None:
            self._client_task.cancel()
            try:
                await self._client_task
            except asyncio.CancelledError:
                _LOGGER.debug("MQTT task succesfully shutdown")

    # endregion

    # region (Un)subscribing

    async def subscribe(
        self, serial: str, callback: Callable[[LetPotDeviceStatus], None]
    ) -> None:
        """Subscribe to devices updates, connecting to the device client and waiting for connection if required."""
        if (
            self._connected is None
            or self._connected.cancelled()
            or (
                self._connected.done()
                and (
                    self._connected.exception() is not None
                    or self._connected.result() is False
                )
            )
        ):
            self._connected = asyncio.get_event_loop().create_future()
            self._client_task = asyncio.create_task(self._connect())
            await self._connected
        elif not self._connected.done():
            await self._connected

        try:
            assert self._client is not None
            topic = f"{serial}/data"

            _LOGGER.debug(f"Subscribing to {topic}")
            await self._client.subscribe(topic)
            self._topics.append(topic)
            self._device_callbacks[serial] = callback
        except aiomqtt.MqttError as err:
            if len(self._topics) == 0:
                await self._disconnect()
            raise err

    async def unsubscribe(self, serial: str) -> None:
        """Unsubscribes from device updates, and cancels the active device client connection if required."""
        topic = f"{serial}/data"
        if topic in self._topics:
            _LOGGER.debug(f"Unsubscribing from {topic}")
            if self._client is not None:
                await self._client.unsubscribe(topic)
            self._topics.remove(topic)
            self._device_callbacks.pop(serial, None)

            if len(self._topics) == 0:
                _LOGGER.debug("Disconnecting because no more topics remain")
                await self._disconnect()

    # endregion

    # region Device functions

    def device_info(self, serial: str) -> LetPotDeviceInfo:
        """Get information about a device model."""
        converter = self._converter(serial)
        device_model = converter.get_device_model()
        return LetPotDeviceInfo(
            model=serial[:5],
            model_name=device_model[0] if device_model else None,
            model_code=device_model[1] if device_model else None,
            features=converter.supported_features(),
        )

    def get_light_brightness_levels(self, serial: str) -> list[int]:
        """Get the light brightness levels for this device."""
        return self._converter(serial).get_light_brightness_levels()

    async def request_status_update(self, serial: str) -> None:
        """Request the device to send the current device status."""
        await self._publish(
            serial, self._converter(serial).get_current_status_message()
        )

    async def get_current_status(self, serial: str) -> LetPotDeviceStatus | None:
        """Request an update of and return the current device status."""
        status_event = asyncio.Event()
        self._device_status_event[serial] = status_event
        await self.request_status_update(serial)
        await status_event.wait()
        return self._device_status_last.get(serial)

    @requires_feature(
        DeviceFeature.LIGHT_BRIGHTNESS_LOW_HIGH, DeviceFeature.LIGHT_BRIGHTNESS_LEVELS
    )
    async def set_light_brightness(self, serial: str, level: int) -> None:
        """Set the light brightness for this device (brightness level)."""
        if level not in self.get_light_brightness_levels(serial):
            raise LetPotFeatureException(
                f"Device doesn't support setting light brightness to {level}"
            )

        status = dataclasses.replace(
            self._get_publish_status(serial), light_brightness=level
        )
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.CATEGORY_HYDROPONIC_GARDEN)
    async def set_light_mode(self, serial: str, mode: LightMode) -> None:
        """Set the light mode for this device (flower/vegetable)."""
        status = dataclasses.replace(self._get_publish_status(serial), light_mode=mode)
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.CATEGORY_HYDROPONIC_GARDEN)
    async def set_light_schedule(
        self, serial: str, start: time | None, end: time | None
    ) -> None:
        """Set the light schedule for this device (start time and/or end time)."""
        use_status = self._get_publish_status(serial)
        start_time = use_status.light_schedule_start if start is None else start
        end_time = use_status.light_schedule_end if end is None else end
        status = dataclasses.replace(
            use_status,
            light_schedule_start=start_time,
            light_schedule_end=end_time,
        )
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.CATEGORY_HYDROPONIC_GARDEN)
    async def set_plant_days(self, serial: str, days: int) -> None:
        """Set the plant days counter for this device (number of days)."""
        status = dataclasses.replace(self._get_publish_status(serial), plant_days=days)
        await self._publish_status(serial, status)

    async def set_power(self, serial: str, on: bool) -> None:
        """Set the general power for this device (on/off)."""
        status = dataclasses.replace(self._get_publish_status(serial), system_on=on)
        await self._publish_status(serial, status)

    async def set_pump_mode(self, serial: str, on: bool) -> None:
        """Set the pump mode for this device (on (scheduled)/off)."""
        status = dataclasses.replace(
            self._get_publish_status(serial), pump_mode=1 if on else 0
        )
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.CATEGORY_HYDROPONIC_GARDEN)
    async def set_sound(self, serial: str, on: bool) -> None:
        """Set the alarm sound for this device (on/off)."""
        status = dataclasses.replace(self._get_publish_status(serial), system_sound=on)
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.TEMPERATURE_SET_UNIT)
    async def set_temperature_unit(self, serial: str, unit: TemperatureUnit) -> None:
        """Set the temperature unit for this device (Celsius/Fahrenheit)."""
        status = dataclasses.replace(
            self._get_publish_status(serial), temperature_unit=unit
        )
        await self._publish_status(serial, status)

    @requires_feature(DeviceFeature.PUMP_AUTO)
    async def set_water_mode(self, serial: str, on: bool) -> None:
        """Set the automatic water/nutrient mode for this device (on/off)."""
        status = dataclasses.replace(
            self._get_publish_status(serial), water_mode=1 if on else 0
        )
        await self._publish_status(serial, status)

    # endregion
