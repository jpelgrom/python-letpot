# python-letpot

Asynchronous Python client for interacting with LetPot hydroponic gardens and watering systems via the manufacturer's cloud. You can listen for status updates (push) and change device settings.

The following models should be supported, although only LPH-AIR is tested:

 - Hydroponic gardens
   - LPH-AIR
   - LPH-MAX
   - LPH-MINI
   - LPH-PRO
   - LPH-SE
 - Watering systems
   - DI-2/DI-3 (Automatic Watering System 2.0)

## Example usage

```python
import aiohttp
import asyncio

from letpot.client import LetPotClient
from letpot.deviceclient import LetPotDeviceClient


async def main():
    async with aiohttp.ClientSession() as session:
        client = LetPotClient(session)

        auth = await client.login("email@example.com", "password")
        # store auth for future use, and use in constructor

        devices = await client.get_devices()
        print(devices)

        device_client = LetPotDeviceClient(auth)
        device_serial = devices[0].serial_number
        await device_client.subscribe(device_serial, lambda status: print(status))
        await device_client.request_status_update(device_serial)
        
        # do work, and finally
        device_client.unsubscribe(device_serial)


asyncio.run(main())
```