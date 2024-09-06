# PyEVELib
An async library to access the Static Data Export (SDE) and EVE Swagger Interface (ESI) in a unified way.

###  Features
* It's async.
* Can download the SDE, unpack it automatically, and check if the current SDE is out of date.
* Doesn't require the SDE, and can use ESI for info instead.
* Supports ESI ratelimiting.
* Caches ESI requests by default, supports both route expiries and ETags.

### Requirements
* Python 3.10+
* aiohttp
* PyYAML

### How to use
```python
import asyncio
from evelib import EVEAPI

async def main():
    eve = EVEAPI()
    # If you want to use the SDE.
    eve.sde.update_sde()  # This checks for updates, downloads, and unpacks the SDE as needed.
    eve.load_sde()  # Loads the SDE from disk.
    
    resolved = await eve.resolve_universe_ids(["Jita"])
    jita_id = resolved.systems["Jita"]
    jita = await eve.get_solarsystem(jita_id)
    print(f"{jita.name}, {jita.id}, {jita.security}")
```
