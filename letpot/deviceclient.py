"""Python client for LetPot hydroponic gardens."""

import asyncio
import dataclasses
from datetime import time
from hashlib import md5, sha256
import logging
import os
import time as systime
import ssl
from typing import Callable
import aiomqtt

from letpot.converters import CONVERTERS, LetPotDeviceConverter
from letpot.exceptions import LetPotAuthenticationException, LetPotException
from letpot.models import AuthenticationInfo, LetPotDeviceStatus

_LOGGER = logging.getLogger(__name__)


def _create_ssl_context() -> ssl.SSLContext:
    """Create a SSL context for the MQTT connection, avoids a blocking call later."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_default_certs()
    return context


_SSL_CONTEXT = _create_ssl_context()


class LetPotDeviceClient:
    """Client for connecting to LetPot device."""

    BROKER_HOST = "broker.letpot.net"
    MTU = 128

    _client: aiomqtt.Client | None = None
    _client_task: asyncio.Task | None = None
    _connected: asyncio.Future[bool] | None = None
    _converter: LetPotDeviceConverter | None = None
    _message_id: int = 0

    _user_id: str
    _email: str
    _device_serial: str
    device_type: str
    device_model_name: str | None = None
    device_model_code: str | None = None

    _update_status: LetPotDeviceStatus | None = None
    _update_clear: asyncio.Task | None = None
    _status_event: asyncio.Event | None = None
    last_status: LetPotDeviceStatus | None = None

    def __init__(self, info: AuthenticationInfo, device_serial: str) -> None:
        self._user_id = info.user_id
        self._email = info.email
        self._device_serial = device_serial

        device_type = self._device_serial[:5]
        for converter in CONVERTERS:
            if converter.supports_type(device_type):
                self._converter = converter(device_type)
                device_model = self._converter.get_device_model()
                if device_model is not None:
                    self.device_model_name = device_model[0]
                    self.device_model_code = device_model[1]
                break

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

    def _handle_message(
        self, message: aiomqtt.Message, callback: Callable[[LetPotDeviceStatus], None]
    ) -> None:
        """Process incoming messages from the broker."""
        if self._converter is None:
            return

        try:
            status = self._converter.convert_hex_to_status(message.payload)
            if status is not None:
                self._update_status = None
                self.last_status = status
                callback(status)
                if self._status_event is not None and not self._status_event.is_set():
                    self._status_event.set()
        except Exception:  # noqa: BLE001
            _LOGGER.warning("Exception while handling message, ignoring", exc_info=True)

    async def _publish(self, message: list[int]) -> None:
        """Publish a message to the device command topic."""
        if self._client is None:
            raise LetPotException("Missing client to publish message with")

        messages = self._generate_message_packets(
            1, 19, message
        )  # maintype 1: data, subtype 19: custom
        topic = f"{self._device_serial}/cmd"
        for publish_message in messages:
            await self._client.publish(topic, payload=publish_message)

    def _get_publish_status(self) -> LetPotDeviceStatus:
        """Get the device status for publishing (pending update or latest)."""
        if self._update_status is not None:
            return self._update_status
        elif self.last_status is not None:
            return self.last_status
        else:
            raise LetPotException("Client doesn't have a status for publishing")

    async def _clear_update_status(self) -> None:
        """Clear the update status after a timeout, to prevent an out of date status."""
        await asyncio.sleep(5)
        self._update_status = None
        self._update_clear = None

    async def _publish_status(self, status: LetPotDeviceStatus) -> None:
        """Set the device status."""
        if self._converter is None or self._client is None:
            raise LetPotException("Missing converter/client to publish message with")

        if self._update_clear is not None:
            self._update_clear.cancel()
            try:
                await self._update_clear
            except asyncio.CancelledError:
                pass
        self._update_status = status
        self._update_clear = asyncio.get_event_loop().create_task(
            self._clear_update_status()
        )
        await self._publish(self._converter.get_update_status_message(status))

    async def _connect_and_subscribe(
        self, callback: Callable[[LetPotDeviceStatus], None]
    ) -> None:
        """Subscribe to state updates for this device."""
        username = f"{self._email}__letpot_v3"
        password = sha256(
            f"{self._user_id}|{md5(username.encode()).hexdigest()}".encode()
        ).hexdigest()
        connection_attempts = 0
        while self._converter is not None:
            try:
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
                    self._client = client
                    self._message_id = 0
                    connection_attempts = 0

                    await client.subscribe(f"{self._device_serial}/data")
                    if self._connected is not None and not self._connected.done():
                        self._connected.set_result(True)

                    async for message in client.messages:
                        self._handle_message(message, callback)
            except aiomqtt.MqttError as err:
                self._client = None

                if isinstance(err, aiomqtt.MqttCodeError):
                    if err.rc in [4, 5, 134, 135]:
                        msg = "MQTT auth error"
                        _LOGGER.error("%s: %s", msg, err)
                        auth_exception = LetPotAuthenticationException(msg)
                        if self._connected is not None and not self._connected.done():
                            self._connected.set_exception(auth_exception)
                        raise auth_exception from err

                connection_attempts += 1
                reconnect_interval = min(connection_attempts * 15, 600)
                _LOGGER.error(
                    "MQTT error, reconnecting in %i seconds: %s",
                    reconnect_interval,
                    err,
                )

                await asyncio.sleep(reconnect_interval)
            finally:
                self._client = None
                if self._connected is not None and not self._connected.done():
                    self._connected.set_result(False)

    async def subscribe(self, callback: Callable[[LetPotDeviceStatus], None]) -> None:
        """Connect to the device client and wait for connection or raise an authentication failure."""
        self._connected = asyncio.get_event_loop().create_future()
        self._client_task = asyncio.create_task(self._connect_and_subscribe(callback))
        await self._connected

    def disconnect(self) -> None:
        """Cancels the active device client connection, if any."""
        if self._client_task is not None:
            self._client_task.cancel()

    def get_light_brightness_levels(self) -> list[int]:
        """Get the light brightness levels for this device."""
        if self._converter is None:
            return []
        else:
            return self._converter.get_light_brightness_levels()

    async def request_status_update(self) -> None:
        """Request the device to send the current device status."""
        if self._converter is None:
            raise LetPotException("Missing converter to build request message")
        await self._publish(self._converter.get_current_status_message())

    async def get_current_status(self) -> LetPotDeviceStatus | None:
        """Request an update of and return the current device status."""
        self._status_event = asyncio.Event()
        await self.request_status_update()
        await self._status_event.wait()
        return self.last_status

    async def set_light_brightness(self, level: int) -> None:
        """Set the light brightness for this device (brightness level)."""
        if level not in self.get_light_brightness_levels():
            raise LetPotException(
                f"Device doesn't support setting light brightness to {level}"
            )

        status = dataclasses.replace(self._get_publish_status(), light_brightness=level)
        await self._publish_status(status)

    async def set_light_mode(self, mode: int) -> None:
        """Set the light mode for this device (flower/vegetable)."""
        status = dataclasses.replace(self._get_publish_status(), light_mode=mode)
        await self._publish_status(status)

    async def set_light_schedule(self, start: time | None, end: time | None) -> None:
        """Set the light schedule for this device (start time and/or end time)."""
        use_status = self._get_publish_status()
        start_time = use_status.light_schedule_start if start is None else start
        end_time = use_status.light_schedule_end if end is None else end
        status = dataclasses.replace(
            use_status,
            light_schedule_start=start_time,
            light_schedule_end=end_time,
        )
        await self._publish_status(status)

    async def set_plant_days(self, days: int) -> None:
        """Set the plant days counter for this device (number of days)."""
        status = dataclasses.replace(self._get_publish_status(), plant_days=days)
        await self._publish_status(status)

    async def set_power(self, on: bool) -> None:
        """Set the general power for this device (on/off)."""
        status = dataclasses.replace(self._get_publish_status(), system_on=on)
        await self._publish_status(status)

    async def set_pump_mode(self, on: bool) -> None:
        """Set the pump mode for this device (on (scheduled)/off)."""
        status = dataclasses.replace(
            self._get_publish_status(), pump_mode=1 if on else 0
        )
        await self._publish_status(status)

    async def set_sound(self, on: bool) -> None:
        """Set the alarm sound for this device (on/off)."""
        status = dataclasses.replace(self._get_publish_status(), system_sound=on)
        await self._publish_status(status)
