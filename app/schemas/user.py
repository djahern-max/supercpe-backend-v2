# app/schemas/user.py - FIXED - Pydantic schemas, NOT SQLAlchemy models
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., max_length=200, description="Full name")
    license_number: Optional[str] = Field(
        None, max_length=20, description="CPA license number"
    )


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str = Field(..., min_length=8, description="User password")


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_premium: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for user responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool
    is_premium: bool
    trial_uploads_used: int
    remaining_trial_uploads: int
    created_at: datetime
    last_login: Optional[datetime] = None


class UserProfileResponse(BaseModel):
    """Schema for user profile responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    license_number: Optional[str] = None
    is_verified: bool
    is_premium: bool
    trial_uploads_used: int
    remaining_trial_uploads: int
    created_at: datetime
    last_login: Optional[datetime] = None


class UserAuthResponse(BaseModel):
    """Schema for authenticated user responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    license_number: Optional[str] = None


class PasswordUpdate(BaseModel):
    """Schema for password updates"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class PasswordReset(BaseModel):
    """Schema for password reset requests"""

    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
