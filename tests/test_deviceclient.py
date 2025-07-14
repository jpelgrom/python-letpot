"""Tests for the device client."""

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock, patch

from aiomqtt import Client

import pytest_asyncio
import asyncio

from . import AUTHENTICATION

from letpot.deviceclient import LetPotDeviceClient


class AsyncQueueIterator:
    """A simple iterator which waits for messages in a queue."""

    def __init__(self, queue=None):
        self.queue = queue or asyncio.Queue()
        self.next_call_count = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        self.next_call_count += 1
        item = await self.queue.get()
        if item is StopAsyncIteration:
            raise StopAsyncIteration
        return item


@pytest_asyncio.fixture()
async def mock_aiomqtt() -> AsyncGenerator[MagicMock]:
    """Mock a aiomqtt.Client."""

    with patch("letpot.deviceclient.aiomqtt.Client") as mock_client_class:
        client = MagicMock(spec=Client)
        client.messages = AsyncQueueIterator()

        mock_client_class.return_value.__aenter__.return_value = client

        yield mock_client_class


async def test_subscribe_setup_shutdown(mock_aiomqtt: MagicMock) -> None:
    """Test subscribing/unsubscribing creates a client and shuts it down."""
    device_client = LetPotDeviceClient(AUTHENTICATION, "LPH21ABCD")
    topic = "LPH21ABCD/status"

    # Test subscribing sets up a client + subscription
    await device_client.subscribe(topic, lambda _: None)
    assert device_client._client is not None
    assert (
        device_client._connected is not None
        and device_client._connected.result() is True
    )

    # Test unsubscribing cancels the subscription + shuts down client
    await device_client.unsubscribe(topic)
    assert device_client._client is None
    assert device_client._client_task.cancelled()


async def test_subscribe_multiple(mock_aiomqtt: MagicMock) -> None:
    """Test multiple subscriptions use one client and shuts down only when all are done."""
    device_client = LetPotDeviceClient(AUTHENTICATION, "LPH21ABCD")
    topic1 = "LPH21ABCD/status"
    topic2 = "LPH21DEFG/status"

    await device_client.subscribe(topic1, lambda _: None)
    await device_client.subscribe(topic2, lambda _: None)
    assert device_client._client is not None
    assert device_client._client.subscribe.call_count == 2  # type: ignore[attr-defined]
    # Check number of calls on message queue. Nothing is sent so 1 call = 1 client.
    assert device_client._client.messages.next_call_count == 1  # type: ignore[attr-defined]

    await device_client.unsubscribe(topic1)
    assert device_client._client.unsubscribe.call_count == 1  # type: ignore[attr-defined]
    assert device_client._client is not None

    await device_client.unsubscribe(topic2)
    assert device_client._client is None
    assert device_client._client_task.cancelled()
