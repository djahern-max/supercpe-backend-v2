# app/schemas/cpe_record.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional


class CPERecordBase(BaseModel):
    """Base schema for CPE Record with your specific fields"""

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
        ...,
        max_length=300,
        description="Institution or organization providing the course",
    )
    subject: Optional[str] = Field(
        None, max_length=300, description="Additional subject details or description"
    )


class CPERecordCreate(CPERecordBase):
    """Schema for creating a new CPE Record"""

    pass


class CPERecordUpdate(BaseModel):
    """Schema for updating a CPE Record"""

    date_completed: Optional[date] = None
    course_type: Optional[str] = Field(None, max_length=100)
    subject_area: Optional[str] = Field(None, max_length=200)
    name_of_course: Optional[str] = Field(None, max_length=500)
    educational_provider: Optional[str] = Field(None, max_length=300)
    subject: Optional[str] = Field(None, max_length=300)


class CPERecordResponse(CPERecordBase):
    """Schema for CPE Record responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    is_verified: bool
    verified_by: Optional[int] = None
    verification_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class CPERecordListResponse(BaseModel):
    """Schema for listing CPE Records (simplified view)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    date_completed: date
    course_type: str
    subject_area: str
    name_of_course: str
    educational_provider: str
    is_verified: bool
    created_at: datetime


# Legacy schemas for compatibility with existing CPE system
class LegacyCPERecordResponse(BaseModel):
    """Schema for existing CPE record system compatibility"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cpa_license_number: str
    user_id: Optional[int] = None
    document_filename: str
    original_filename: Optional[str] = None
    cpe_credits: float
    ethics_credits: float
    course_title: Optional[str] = None
    provider: Optional[str] = None
    completion_date: Optional[date] = None
    certificate_number: Optional[str] = None
    confidence_score: Optional[float] = None
    parsing_method: Optional[str] = None
    storage_tier: Optional[str] = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime
