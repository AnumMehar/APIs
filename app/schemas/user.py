
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class UserCreate(BaseModel):
    N_ID: Optional[int] = None  # Optional, auto-assigned
    name: str
    age: int
    gender: str
    national_id: str = Field(..., max_length=20)

    @field_validator("national_id")
    def remove_dashes(cls, v):
        return v.replace("-", "").replace(" ", "")

class UserOut(BaseModel):
    N_ID: int
    name: str
    age: int
    gender: str
    national_id: str
    created_at: Optional[str]

