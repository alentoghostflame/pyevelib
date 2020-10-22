from evelib.types import TypeManager, TypeData
from evelib.universe import RegionData
from datetime import datetime
from typing import Optional, List, Iterator


class ESIServiceUnavailable(Exception):
    pass


class MarketData:
    def __init__(self, region: RegionData, item: TypeData, state: dict):
        self.item: TypeData = item
        self.region: RegionData = region
        self.average: int = 0
        self.highest: int = 0
        self.lowest: int = 0
        self.order_count: int = 0
        self.volume: int = 0
        self.date: Optional[datetime] = None
        if state:
            self.from_state(state)

    def from_state(self, state: dict):
        self.average = state["average"]
        self.highest = state["highest"]
        self.lowest = state["lowest"]
        self.order_count = state["order_count"]
        self.volume = state["volume"]
        self.date = datetime.strptime(state["date"], "%Y-%m-%d")


class MarketHistory:
    def __init__(self, region: RegionData, item: TypeData, json: List[dict] = None):
        self.item = item
        self.location: RegionData = region
        self.oldest: Optional[MarketData] = None
        self.newest: Optional[MarketData] = None
        self.history: List[MarketData] = list()
        self.average = 0
        self.highest = 0
        self.lowest = 0
        self.order_count = 0
        self.volume = 0
        if json:
            self.from_json(json)

    def from_json(self, json: List[dict]):
        average_sum = 0
        for market_data in json:
            data = MarketData(self.location, self.item, market_data)
            self.history.append(data)
            if not self.oldest or data.date < self.oldest.date:
                self.oldest = data
            if not self.newest or self.newest.date < data.date:
                self.newest = data
            average_sum += data.average
            if not self.highest or self.highest < data.highest:
                self.highest = data.highest
            if not self.lowest or data.lowest < self.lowest:
                self.lowest = data.lowest
            self.order_count += data.order_count
            self.volume += data.volume
        self.average = average_sum / len(self.history)

    def __getitem__(self, item: int) -> MarketData:
        return self.history[item]

    def __iter__(self) -> Iterator[MarketData]:
        return iter(self.history)


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
                         8: "Invention", 9: "Composite Reaction", 10: "Reaction 2", 11: "Reaction 3"}
        return activity_dict.get(activity_id, f"Activity not found?? ID: {activity_id}")

