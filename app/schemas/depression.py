
# # from pydantic import BaseModel
# # from typing import List
# # from datetime import datetime
# #
# # class DepressionAnswer(BaseModel):
# #     question_no: int
# #     answer: bool
# #     score: int
# #
# # class DepressionSubmit(BaseModel):
# #     user_uuid: str
# #     answers: List[DepressionAnswer]
#
# class DepressionResponse(BaseModel):
#     Dep_test_id: int
#     user_uuid: str
#     final_scores: int
#     final_result: str
#     created_at: datetime

from pydantic import BaseModel, Field, AliasChoices
from typing import List, Optional
from datetime import datetime

# ---------------- Schema ----------------
class DepressionAnswer(BaseModel):
    question_no: int
    answer: bool
    score: int

class DepressionSubmit(BaseModel):
    user_uuid: Optional[str] = None      # only required for new test
    n_id: Optional[int] = None
    test_id: Optional[int] = None        # required for updates/final submit
    answers: Optional[List[DepressionAnswer]] = None  # optional, for update of questions
    submit_test: Optional[bool] = False     # optional, for final submit

class DepressionResponse(BaseModel):
    Dep_test_id: int
    user_uuid: str
    # n_id: int
    final_scores: int
    final_result: str
    is_submitted: bool
    completed_at: Optional[datetime]
    created_at: datetime

class DepressionOut(BaseModel):
    user_uuid: str = Field(validation_alias=AliasChoices("User_uuid", "user_uuid"))
    # n_id: int = Field(validation_alias=AliasChoices("N_ID", "n_id"))
    final_scores: int = Field(validation_alias=AliasChoices("Final_scores", "final_scores"))
    final_result: str = Field(validation_alias=AliasChoices("Final_result", "final_result"))

    # Add other fields following the same pattern
    dep_test_id: int = Field(validation_alias=AliasChoices("Dep_test_id", "dep_test_id"))
    is_submitted: str = Field(validation_alias=AliasChoices("is_submitted", "is_submitted"))
    completed_at: str = Field(validation_alias=AliasChoices("completed_at", "completed_at"))

    class Config:
        from_attributes = True