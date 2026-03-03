from pydantic import BaseModel
from uuid import UUID
from typing import Optional
from datetime import datetime


# 🔹 Request Schema (used for both round1 and round2)
class PhysicalFrailtyTestCreate(BaseModel):
    # user_uuid: UUID
    n_id: int
    test: str
    value: float


# 🔹 Response Schema (matches Prisma model)
class PhysicalFrailtyResponse(BaseModel):
    # uuid: UUID
    # n_id: int
    User_uuid: UUID
    PF_test_id: int
    created_at: Optional[datetime]

    # Walking Speed
    Walking_speed_r1: Optional[float]
    walking_speed_r1_created_at: Optional[datetime]
    walking_speed_r1_is_done: Optional[bool]

    Walking_speed_r2: Optional[float]
    walking_speed_r2_created_at: Optional[datetime]
    walking_speed_r2_is_done: Optional[bool]

    # Functional Reach
    Functional_reach_r1: Optional[float]
    functional_reach_r1_created_at: Optional[datetime]
    functional_reach_r1_is_done: Optional[bool]

    Functional_reach_r2: Optional[float]
    functional_reach_r2_created_at: Optional[datetime]
    functional_reach_r2_is_done: Optional[bool]

    # Standing On One Leg
    Standing_on_one_leg_r1: Optional[float]
    standing_on_one_leg_r1_created_at: Optional[datetime]
    standing_on_one_leg_r1_is_done: Optional[bool]

    Standing_on_one_leg_r2: Optional[float]
    standing_on_one_leg_r2_created_at: Optional[datetime]
    standing_on_one_leg_r2_is_done: Optional[bool]

    # Time Up And Go
    Time_up_and_go_r1: Optional[float]
    time_up_and_go_r1_created_at: Optional[datetime]
    time_up_and_go_r1_is_done: Optional[bool]

    Time_up_and_go_r2: Optional[float]
    time_up_and_go_r2_created_at: Optional[datetime]
    time_up_and_go_r2_is_done: Optional[bool]

    # Seated Forward Bend
    seated_forward_bend_r1: Optional[float]
    seated_forward_bend_r1_created_at: Optional[datetime]
    seated_forward_bend_r1_is_done: Optional[bool]

    seated_forward_bend_r2: Optional[float]
    seated_forward_bend_r2_created_at: Optional[datetime]
    seated_forward_bend_r2_is_done: Optional[bool]

    class Config:
        from_attributes = True

class PhysicalFrailtyOut(BaseModel):
    Walking_speed_r1: Optional[float]
    walking_speed_r1_created_at: Optional[datetime]
    walking_speed_r1_is_done: Optional[bool]

    Walking_speed_r2: Optional[float]
    walking_speed_r2_created_at: Optional[datetime]
    walking_speed_r2_is_done: Optional[bool]

    # Functional Reach
    Functional_reach_r1: Optional[float]
    functional_reach_r1_created_at: Optional[datetime]
    functional_reach_r1_is_done: Optional[bool]

    Functional_reach_r2: Optional[float]
    functional_reach_r2_created_at: Optional[datetime]
    functional_reach_r2_is_done: Optional[bool]

    # Standing On One Leg
    Standing_on_one_leg_r1: Optional[float]
    standing_on_one_leg_r1_created_at: Optional[datetime]
    standing_on_one_leg_r1_is_done: Optional[bool]

    Standing_on_one_leg_r2: Optional[float]
    standing_on_one_leg_r2_created_at: Optional[datetime]
    standing_on_one_leg_r2_is_done: Optional[bool]

    # Time Up And Go
    Time_up_and_go_r1: Optional[float]
    time_up_and_go_r1_created_at: Optional[datetime]
    time_up_and_go_r1_is_done: Optional[bool]

    Time_up_and_go_r2: Optional[float]
    time_up_and_go_r2_created_at: Optional[datetime]
    time_up_and_go_r2_is_done: Optional[bool]

    # Seated Forward Bend
    seated_forward_bend_r1: Optional[float]
    seated_forward_bend_r1_created_at: Optional[datetime]
    seated_forward_bend_r1_is_done: Optional[bool]

    seated_forward_bend_r2: Optional[float]
    seated_forward_bend_r2_created_at: Optional[datetime]
    seated_forward_bend_r2_is_done: Optional[bool]

    class Config:
        from_attributes = True

