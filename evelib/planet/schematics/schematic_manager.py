import logging
from typing import Optional
import yaml
try:
    from yaml import CSafeLoader as SafeLoader, CSafeDumper as SafeDumper
    print("Managed to import C yaml!")
except ImportError:
    from yaml import SafeLoader, SafeDumper
    print("Import regular yaml")


class SchematicData:
    def __init__(self, schematic: dict = None):
        self.cycle_time: int = 0
        self.id: int = 0
        self.name: str = "Default Schematic Name"

        if schematic:
            self.from_schematic(schematic)

    def from_schematic(self, state: dict):
        self.cycle_time = state["cycleTime"]
        self.id = state["schematicID"]
        self.name = state["schematicName"]


class SchematicManager:
    def __init__(self, logger: logging.Logger, sde_path: str):
        self._logger = logger
        self._sde_path = sde_path

        self._ram_cache: dict = dict()

    def load(self):
        self._logger.debug("Starting to load planetary schematics...")
        file_path = f"{self._sde_path}/bsd/planetSchematics.yaml"
        file = open(file_path, "r")
        raw_data = yaml.load(file, Loader=SafeLoader)
        file.close()
        for raw_schematic_data in raw_data:
            schematic = SchematicData(schematic=raw_schematic_data)
            self._ram_cache[schematic.id] = schematic
        self._logger.debug("Loaded planetary schematics.")

    def get(self, schematic_id: int) -> Optional[SchematicData]:
        return self._ram_cache.get(schematic_id, None)



