"""The owner's unit records, and matching a lease to one of them."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

type UnitStatus = Literal["available", "occupied"]


class Unit(BaseModel, frozen=True):
    unit_id: str
    label: str
    unit_type: str
    status: UnitStatus
    building_id: str
    building_name: str
    property_name: str


def load_units(path: Path) -> list[Unit]:
    """Flatten the owner's property > building > unit file into a list of units."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        Unit(
            unit_id=unit["unit_id"],
            label=unit["label"],
            unit_type=unit["type"],
            status=unit["status"],
            building_id=building["building_id"],
            building_name=building["name"],
            property_name=prop["name"],
        )
        for prop in raw["properties"]
        for building in prop["buildings"]
        for unit in building["units"]
    ]


def find_units(reference: str, units: list[Unit]) -> list[Unit]:
    """Units whose label and building both appear in the lease's wording.

    "Apartment 1204, Tower B, Marina Crest Residences" names exactly one unit.
    Zero or several matches are returned as they are: deciding what an
    ambiguous reference means is the caller's job, not a guess made here.
    """
    text = " ".join(reference.lower().split())
    return [
        unit for unit in units if unit.label.lower() in text and unit.building_name.lower() in text
    ]
