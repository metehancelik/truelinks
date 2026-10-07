"""What the model returns when it looks at photos of a unit."""

from typing import Literal

from pydantic import BaseModel, Field

type Condition = Literal["new", "good", "worn", "damaged"]
type Urgency = Literal["low", "medium", "high"]


class Damage(BaseModel):
    description: str = Field(description="What is damaged and how, in one sentence")
    photo: int = Field(description="Number of the photo that shows it, starting at 1")


class Equipment(BaseModel):
    name: str = Field(description="The item, e.g. 'split AC unit', 'water heater', 'kitchen tap'")
    condition: Condition
    photo: int = Field(description="Number of the photo that shows it, starting at 1")


class WorkOrderDraft(BaseModel):
    title: str = Field(description="Short title a contractor would recognise, under ten words")
    description: str = Field(
        description="What is wrong and what needs doing, two or three sentences"
    )
    urgency: Urgency


class IssueAssessment(BaseModel):
    """Every finding names the photo it came from, so a person can check it."""

    overall_condition: Condition = Field(description="Condition of what the photos show")
    damages: list[Damage] = Field(description="Visible damage. Empty when none is visible.")
    equipment: list[Equipment] = Field(description="Contents and equipment visible in the photos")
    work_order: WorkOrderDraft
