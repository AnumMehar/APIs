from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from app.schemas.depression import DepressionAnswer
from app.schemas.dementia import DementiaQuestion
from typing import Optional, List


class ReportResponse(BaseModel):
    uuid: UUID
    Report_test_id: int
    user_uuid: UUID

    Dep_test_id: Optional[int]
    Dem_test_id: Optional[int]
    PF_test_id: Optional[int]

    created_at: datetime
    remarks: Optional[str] = None

    class Config:
        from_attributes = True
class UpdateReportPayload(BaseModel):
    depression_answers: Optional[List[DepressionAnswer]] = None
    dementia_answers: Optional[List[DementiaQuestion]] = None
    remarks: Optional[str] = None
