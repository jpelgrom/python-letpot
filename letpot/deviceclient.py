import asyncio
import dataclasses
from hashlib import md5, sha256
import os
import time as systime
import aiomqtt

from letpot.converters import *
from letpot.models import AuthenticationInfo, LetPotDeviceStatus


class LetPotDeviceClient:
    """Client for connecting to LetPot device."""

    BROKER_HOST = "broker.letpot.net"
    MTU = 128

    _client: aiomqtt.Client | None = None
    _converter: LetPotDeviceConverter | None = None
    _message_id: int = 0
    _user_id: str | None = None
    _email: str | None = None
    _device_serial: str | None = None
    last_status: LetPotDeviceStatus | None = None

    def __init__(self, info: AuthenticationInfo, device_serial: str) -> None:
        self._user_id = info.user_id
        self._email = info.email
        self._device_serial = device_serial

        device_type = self._device_serial[:5]
        if LPHx1Converter.supports_type(device_type):
            self._converter = LPHx1Converter
        elif IGSorAltConverter.supports_type(device_type):
            self._converter = IGSorAltConverter
        elif LPH6xConverter.supports_type(device_type):
            self._converter = LPH6xConverter
        elif LPH63Converter.supports_type(device_type):
            self._converter = LPH63Converter

    def _generate_client_id(self) -> str:
        """Generate a client identifier for the connection."""
        return f"LetPot_{round(systime.time() * 1000)}_{os.urandom(4).hex()[:8]}"
    
    def _generate_message_packets(self, type: int, subtype: int, message: list[int]) -> list[str]:
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
                    (subtype << 2) | type,
                    16,
                    self._message_id,
                    len(payload) + 4,
                    length % 256,
                    length // 256,
                    *payload
                ]
            else:
                packet = [
                    (subtype << 2) | type,
                    0,
                    self._message_id,
                    len(payload),
                    *payload
                ]

            packets.append(''.join(f'{byte:02x}' for byte in packet))
            self._message_id += 1

        return packets

    async def _handle_messages(self, callback: callable) -> None:
        """Process incoming messages from the broker."""
        async for message in self._client.messages:
            print(f"{message.topic} received: {message.payload}")
            if self._converter is not None:
                status = self._converter.convert_hex_to_status(message.payload)
                if status is not None:
                    self.last_status = status
                    callback(status)
    
    async def _publish(self, message: list[int]) -> None:
        """Publish a message to the device command topic."""
        if self._client is None:
            raise Exception("Missing client to publish message with")
        
        messages = self._generate_message_packets(1, 19, message) # type 1: data, subtype 19: custom
        topic = f"{self._device_serial}/cmd"
        for publish_message in messages:
            await self._client.publish(topic, payload=publish_message)
            print(f"{topic} published: {publish_message}")

    async def subscribe(self, callback: callable) -> None:
        """Subscribe to state updates for this device."""
        username = f"{self._email}__letpot_v3"
        password = sha256(f"{self._user_id}|{md5(username.encode()).hexdigest()}".encode()).hexdigest()
        reconnect_interval = 10
        while True:
            try:
                async with aiomqtt.Client(
                    hostname=self.BROKER_HOST,
                    port=443,
                    username=username,
                    password=password,
                    identifier=self._generate_client_id(),
                    protocol=aiomqtt.ProtocolVersion.V5,
                    transport="websockets",
                    tls_params=aiomqtt.TLSParameters(),
                    websocket_path="/mqttwss"
                ) as client, asyncio.TaskGroup() as tg:
                    self._client = client
                    self._message_id = 0
                    
                    await client.subscribe(f"{self._device_serial}/data")
                    print("Client is subscribed and awaiting statuses...")
                    
                    tg.create_task(self._handle_messages(callback))
                    tg.create_task(self._publish(self._converter.get_current_status_message()))
            except aiomqtt.MqttError as e:
                print(f"Connection lost: {e}")
                self._client = None
                await asyncio.sleep(reconnect_interval)
            finally:
                self._client = None

    async def set_light_brightness(self, level: int) -> None:
        """Set the light brightness for this device (brightness level)."""
        device_type = self._device_serial[:5]
        if level not in self._converter.get_light_brightness_levels(device_type):
            raise Exception(f"Device doesn't support setting light brightness to {level}")
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, light_brightness=level)
        await self._publish(self._converter.get_update_status_message(new_status))
        
    async def set_light_mode(self, mode: int) -> None:
        """Set the light mode for this device (flower/vegetable)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, light_mode=mode)
        await self._publish(self._converter.get_update_status_message(new_status))

    async def set_light_schedule(self, start: time, end: time) -> None:
        """Set the light schedule for this device (start time-end time)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(
            self.last_status,
            light_schedule_start=start,
            light_schedule_end=end
        )
        await self._publish(self._converter.get_update_status_message(new_status))

    async def set_plant_days(self, days: int) -> None:
        """Set the plant days counter for this device (number of days)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, plant_days=days)
        await self._publish(self._converter.get_update_status_message(new_status))

    async def set_power(self, on: bool) -> None:
        """Set the general power for this device (on/off)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, system_on=on)
        await self._publish(self._converter.get_update_status_message(new_status))

    async def set_pump_mode(self, on: bool) -> None:
        """Set the pump mode for this device (on (scheduled)/off)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, pump_mode=1 if on else 0)
        await self._publish(self._converter.get_update_status_message(new_status))

    async def set_sound(self, on: bool) -> None:
        """Set the alarm sound for this device (on/off)."""
        if self.last_status is None:
            raise Exception("Client doesn't have a status to update")
        
        new_status = dataclasses.replace(self.last_status, system_sound=on)
        await self._publish(self._converter.get_update_status_message(new_status))