# app/schemas/admin.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional


# ============================================================
# CREATE DOCTOR
# ============================================================

class CreateDoctorSchema(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)


# ============================================================
# RESET DOCTOR PASSWORD
# ============================================================

class ResetDoctorPasswordSchema(BaseModel):
    new_password: str = Field(..., min_length=6)


# ============================================================
# CHANGE OWN PASSWORD (Doctor + Super Admin)
# ============================================================

class ChangePasswordSchema(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6)


# ============================================================
# ASSIGN DOCTOR TO PATIENT
# ============================================================

class AssignDoctorSchema(BaseModel):
    doctor_uuid: str


# ============================================================
# UPDATE USER
# ============================================================

class EditUserSchema(BaseModel):
    name: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    national_id: Optional[str]

# ============================================================
# DELETE DOCTOR
# ============================================================
class DeleteDoctorSchema(BaseModel):
    email: str