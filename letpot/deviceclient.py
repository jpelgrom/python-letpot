import asyncio
from hashlib import md5, sha256
import os
import time
import aiomqtt

from letpot.converters import LPH21Converter
from letpot.models import AuthenticationInfo


class LetPotDeviceClient:
    """Client for connecting to LetPot device."""

    BROKER_HOST = "broker.letpot.net"

    _client: aiomqtt.Client | None = None
    _user_id: str | None = None
    _email: str | None = None
    _device_serial: str | None = None

    def __init__(self, info: AuthenticationInfo, device_serial: str) -> None:
        self._user_id = info.user_id
        self._email = info.email
        self._device_serial = device_serial

    def _generate_client_id(self) -> str:
        """Generate a client identifier for the connection."""
        return f"LetPot_{round(time.time() * 1000)}_{os.urandom(4).hex()[:8]}"

    async def subscribe(self, callback: callable) -> None:
        """Subscribe to state updates for this device."""
        username = f"{self._email}__letpot_v3"
        password = sha256(f"{self._user_id}|{md5(username.encode()).hexdigest()}".encode()).hexdigest()
        while True:
            try:
                async with aiomqtt.Client(
                    hostname = self.BROKER_HOST,
                    port=443,
                    username=username,
                    password=password,
                    identifier=self._generate_client_id(),
                    protocol=aiomqtt.ProtocolVersion.V5,
                    transport="websockets",
                    tls_params=aiomqtt.TLSParameters(),
                    websocket_path="/mqttwss"
                ) as client:
                    self._client = client
                    device_type = self._device_serial[:5]

                    await client.subscribe(f"{self._device_serial}/data")
                    print("Client is subscribed and awaiting statuses...")

                    async for message in client.messages:
                        print(f"{message.topic} received: {message.payload}")
                        # todo make me loop through all converters
                        if LPH21Converter.supports_type(device_type):
                            status = LPH21Converter.convert_hex_to_status(message.payload)
                            callback(status)

            except aiomqtt.MqttError as e:
                print(f"Connection lost: {e}")
                self._client = None
                await asyncio.sleep(10)
            finally:
                self._client = None