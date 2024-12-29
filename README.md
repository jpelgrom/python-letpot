# python-letpot

Python client for LetPot hydrophonic gardens.

The following models should be supported, although only LPH-AIR is tested:

 - LPH-AIR
 - LPH-MAX
 - LPH-MINI
 - LPH-PRO
 - LPH-SE

## Example usage

```python
from letpot.client import LetPotClient
from letpot.deviceclient import LetPotDeviceClient

async with aiohttp.ClientSession() as session:
    client = LetPotClient(session)

    auth = await client.login("email@example.com", "password")
    # store auth for future use, and use in constructor

    devices = await client.get_devices()
    print(devices)

    device_client = LetPotDeviceClient(info=auth, device_serial=devices[0].serial_number)
    await device_client.subscribe(lambda status : print(status))
```