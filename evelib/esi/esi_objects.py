from evelib.types import TypeManager, TypeData
from datetime import datetime
from typing import Optional


class ESIServiceUnavailable(Exception):
    pass


class IndustryJob:
    def __init__(self, type_manager: TypeManager = None, state: dict = None):
        self.activity_id: int = 0
        self.activity_string: str = ""
        self.blueprint_id: int = 0
        self.blueprint_location_id: int = 0
        self.blueprint_type_id: int = 0
        self.blueprint_type: Optional[TypeData] = None
        self.cost: float = 0.0
        self.end_date_string: str = ""
        self.end_date: Optional[datetime] = None
        self.facility_id: int = 0
        self.installer_id: int = 0
        self.licensed_runs: int = 0
        self.probability: float = 0.0
        self.product_type_id: int = 0
        self.product_type: Optional[TypeData] = None
        self.runs: int = 4
        self.start_date_string: str = ""
        self.start_date: Optional[datetime] = None
        self.station_id: int = 0
        self.status: str = ""

        if state:
            self.from_dict(type_manager, state)

    def from_dict(self, type_manager: TypeManager, state: dict):
        self.activity_id = state["activity_id"]
        self.activity_string = self.get_activity(self.activity_id)
        self.blueprint_id = state["blueprint_id"]
        self.blueprint_location_id = state["blueprint_location_id"]
        self.blueprint_type_id = state["blueprint_type_id"]
        self.blueprint_type = type_manager.get_type(self.blueprint_type_id)
        self.cost = state["cost"]
        self.end_date_string = state["end_date"]
        self.end_date = datetime.strptime(self.end_date_string, "%Y-%m-%dT%H:%M:%SZ")
        self.facility_id = state["facility_id"]
        self.installer_id = state["installer_id"]
        self.licensed_runs = state["licensed_runs"]
        self.probability = state["probability"]
        self.product_type_id = state["product_type_id"]
        self.product_type = type_manager.get_type(self.product_type_id)
        self.runs = state["runs"]
        self.start_date_string = state["start_date"]
        self.start_date = datetime.strptime(self.start_date_string, "%Y-%m-%dT%H:%M:%SZ")
        self.station_id = state["station_id"]
        self.status = state["status"]

    # noinspection PyMethodMayBeStatic
    def get_activity(self, activity_id: int) -> str:
        activity_dict = {0: "None", 1: "Manufacturing", 3: "Researching Time Efficiency",
                         4: "Researching Material Efficiency", 5: "Copying", 7: "Reverse Engineering",
                         8: "Invention", 11: "Reactions"}
        return activity_dict.get(activity_id, f"Activity not found?? ID: {activity_id}")

