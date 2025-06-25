# app/schemas/auth.py
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from app.schemas.user import UserResponse


class LoginRequest(BaseModel):
    """Schema for login requests"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="User password")


class SignupRequest(BaseModel):
    """Schema for user registration"""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="User password")
    full_name: str = Field(..., max_length=200, description="Full name")
    license_number: str = Field(..., max_length=20, description="CPA license number")


class TokenResponse(BaseModel):
    """Schema for token responses"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class PasswordUpdate(BaseModel):
    """Schema for password updates"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class PasswordResetRequest(BaseModel):
    """Schema for password reset requests"""

    email: EmailStr = Field(..., description="User email address")


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")


class EmailVerificationRequest(BaseModel):
    """Schema for email verification requests"""

    token: str = Field(..., description="Email verification token")


# License verification schemas
class LicenseVerificationRequest(BaseModel):
    """Schema for license verification"""

    license_number: str = Field(..., max_length=20, description="CPA license number")
    last_name: str = Field(..., max_length=100, description="Last name on license")


class LicenseVerificationResponse(BaseModel):
    """Schema for license verification response"""

    is_valid: bool
    license_number: str
    full_name: Optional[str] = None
    expiration_date: Optional[str] = None
    status: Optional[str] = None
    message: str
