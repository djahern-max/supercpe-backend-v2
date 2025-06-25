# app/schemas/user.py
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    """Base user schema"""

    email: EmailStr = Field(..., description="User email address")
    license_number: str = Field(..., max_length=20, description="CPA license number")
    full_name: str = Field(..., max_length=200, description="Full name")


class UserCreate(UserBase):
    """Schema for creating a new user"""

    password: str = Field(..., min_length=8, description="User password")


class UserUpdate(BaseModel):
    """Schema for updating a user"""

    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=200)
    license_number: Optional[str] = Field(None, max_length=20)


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
    updated_at: datetime
    last_login: Optional[datetime] = None


class UserProfileResponse(UserResponse):
    """Extended user profile response with subscription info"""

    can_upload: bool
    subscription_status: Optional[str] = None


class UserAuthResponse(BaseModel):
    """Schema for authentication responses"""

    access_token: str
    token_type: str
    user: UserResponse


class PasswordUpdate(BaseModel):
    """Schema for password updates"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class PasswordReset(BaseModel):
    """Schema for password reset"""

    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
