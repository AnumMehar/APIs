# from pydantic import BaseModel
# from typing import List
# from datetime import datetime
#
# class DementiaQuestion(BaseModel):
#     no: int
#     answer: str
#     possible: int
#     earned: int
#
# class DementiaSubmit(BaseModel):
#     user_uuid: str
#     questions: List[DementiaQuestion]

# class DementiaResponse(BaseModel):
#     dem_test_id: int
#     user_uuid: str
#     total_earned_point: int
#     final_result: str
#     created_at: datetime


from pydantic import BaseModel, Field, AliasChoices
from typing import List,  Optional
from datetime import datetime

# ---------------- Schema ----------------
class DementiaQuestion(BaseModel):
    no: int
    answer: str
    possible: int
    earned: int

class DementiaSubmit(BaseModel):
    user_uuid: Optional[str] = None       # required only for new test
    n_id: Optional[int] = None
    test_id: Optional[int] = None         # required for updates/final submit
    questions: Optional[List[DementiaQuestion]] = None  # optional for submit
    submit_test: Optional[bool] = False       # optional, final submit

class DementiaResponse(BaseModel):
    dem_test_id: int
    user_uuid: str
    total_earned_point: int
    final_result: str
    completed_at: Optional[datetime]
    created_at: datetime
    created_at: datetime

class DementiaOut(BaseModel):
    user_uuid: str = Field(validation_alias=AliasChoices("User_uuid", "user_uuid"))
    # Use Optional if the test might not be finished yet
    total_earned_point: Optional[int] = Field(None, validation_alias=AliasChoices("Total_earned_point", "total_earned_point"))
    final_result: Optional[str] = Field(None, validation_alias=AliasChoices("Final_result", "final_result"))
    dem_test_id: int = Field(validation_alias=AliasChoices("Dem_test_id", "dem_test_id"))
    is_submitted: str = Field(validation_alias=AliasChoices("is_submitted", "is_submitted"))
    completed_at: str = Field(validation_alias=AliasChoices("completed_at", "completed_at"))

    class Config:
        from_attributes = True