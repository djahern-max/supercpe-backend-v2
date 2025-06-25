# app/schemas/cpe_record.py - FIXED - Pydantic schemas, NOT SQLAlchemy models
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional


class CPERecordBase(BaseModel):
    """Base CPE record schema"""

    date_completed: date = Field(..., description="Date when the course was completed")
    course_type: str = Field(
        ..., max_length=100, description="Type/category of the course"
    )
    subject_area: str = Field(
        ..., max_length=200, description="Subject area or field of study"
    )
    name_of_course: str = Field(
        ..., max_length=500, description="Full name/title of the course"
    )
    educational_provider: str = Field(
        ..., max_length=300, description="Institution providing the course"
    )
    subject: Optional[str] = Field(
        None, max_length=300, description="Additional subject details"
    )


class CPERecordCreate(CPERecordBase):
    """Schema for creating a new CPE record"""

    pass


class CPERecordUpdate(BaseModel):
    """Schema for updating a CPE record"""

    date_completed: Optional[date] = None
    course_type: Optional[str] = Field(None, max_length=100)
    subject_area: Optional[str] = Field(None, max_length=200)
    name_of_course: Optional[str] = Field(None, max_length=500)
    educational_provider: Optional[str] = Field(None, max_length=300)
    subject: Optional[str] = Field(None, max_length=300)
    is_verified: Optional[bool] = None


class CPERecordResponse(CPERecordBase):
    """Schema for CPE record responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_verified: bool
    verified_by: Optional[int] = None
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CPERecordListResponse(BaseModel):
    """Schema for CPE record list responses (simplified)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date_completed: date
    course_type: str
    name_of_course: str
    educational_provider: str
    is_verified: bool
    created_at: datetime


class LegacyCPERecordResponse(BaseModel):
    """Schema for legacy CPE record responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date_completed: date
    course_type: str
    subject_area: str
    name_of_course: str
    educational_provider: str
    subject: Optional[str] = None
