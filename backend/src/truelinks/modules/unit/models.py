from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from truelinks.modules.unit.records import Unit, UnitStatus
from truelinks.platform.db import Base


class UnitRow(Base):
    __tablename__ = "units"

    # A unit id is only unique within one owner: two owners may both have an
    # "Apartment 1204". The key is the pair, never the unit id alone.
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    unit_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str]
    unit_type: Mapped[str]
    status: Mapped[str]
    building_id: Mapped[str]
    building_name: Mapped[str]
    property_name: Mapped[str]

    def to_unit(self) -> Unit:
        status: UnitStatus = "occupied" if self.status == "occupied" else "available"
        return Unit(
            unit_id=self.unit_id,
            label=self.label,
            unit_type=self.unit_type,
            status=status,
            building_id=self.building_id,
            building_name=self.building_name,
            property_name=self.property_name,
        )


def list_units(session: Session, tenant_id: str) -> list[UnitRow]:
    query = select(UnitRow).where(UnitRow.tenant_id == tenant_id).order_by(UnitRow.unit_id)
    return list(session.scalars(query))


def get_unit(session: Session, tenant_id: str, unit_id: str) -> UnitRow | None:
    return session.get(UnitRow, (tenant_id, unit_id))


def seed_units(session: Session, tenant_id: str, units: list[Unit]) -> None:
    """Load the owner's unit file once; later starts keep the stored occupancy."""
    if list_units(session, tenant_id):
        return
    session.add_all(UnitRow(tenant_id=tenant_id, **unit.model_dump()) for unit in units)
    session.commit()
