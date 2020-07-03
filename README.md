# EVE-Python-Library
A library to help people easily access the Static Data Export (SDE) and EVE Swagger Interface (ESI)

####  Features
* Get region or solar system data from an int ID or string.
* Get basic type/item information from an int ID or string.
* In-progress ESI functionality.

#### Requirements
* Python 3
* AIOHTTP
* PyYAML

#### How to use
```python
from evelib import EVEManager, SolarSystemData
eve_manager = EVEManager()
eve_manager.load()

planet_data: SolarSystemData = eve_manager.universe.get_any(30004259)
print(planet_data.name)

eve_manager.save()
```
