# app/schemas/cpa.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime
from typing import Optional


class CPABase(BaseModel):
    """Base CPA schema"""

    license_number: str = Field(..., max_length=20, description="CPA license number")
    full_name: str = Field(..., max_length=200, description="Full name of the CPA")
    license_issue_date: date = Field(..., description="Date when license was issued")
    license_expiration_date: date = Field(..., description="Date when license expires")
    status: Optional[str] = Field(
        None, max_length=50, description="License status (Active, Inactive, etc.)"
    )
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    phone: Optional[str] = Field(None, max_length=20, description="Phone number")


class CPACreate(CPABase):
    """Schema for creating a new CPA"""

    passcode: Optional[str] = Field(
        None, max_length=12, description="Generated passcode for CPA"
    )


class CPAUpdate(BaseModel):
    """Schema for updating a CPA"""

    full_name: Optional[str] = Field(None, max_length=200)
    license_issue_date: Optional[date] = None
    license_expiration_date: Optional[date] = None
    status: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    is_premium: Optional[bool] = None
    total_cpe_hours: Optional[int] = None
    ethics_hours: Optional[int] = None


class CPAResponse(CPABase):
    """Schema for CPA responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    passcode: Optional[str] = None
    is_premium: bool
    total_cpe_hours: int
    ethics_hours: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_oplc_sync: Optional[datetime] = None


class CPAListResponse(BaseModel):
    """Schema for CPA list responses (simplified)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    license_number: str
    full_name: str
    license_expiration_date: date
    status: str
    is_premium: bool
    total_cpe_hours: int
    ethics_hours: int


class CPASearchResult(BaseModel):
    """Schema for CPA search results"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    license_number: str
    full_name: str
    status: str
    license_expiration_date: date
