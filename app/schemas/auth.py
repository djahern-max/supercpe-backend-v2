# app/schemas/auth.py - Clean and simple auth schemas
from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class LoginRequest(BaseModel):
    """Standard login with email and password"""

    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    """Signup with email, password, and license verification"""

    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )
    full_name: str = Field(..., min_length=2, max_length=200)
    license_number: str = Field(..., min_length=3, max_length=20)


class PasscodeSignupRequest(BaseModel):
    """Signup using CPA passcode (no password required initially)"""

    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=200)
    passcode: str = Field(..., min_length=6, max_length=12)


class SetPasswordRequest(BaseModel):
    """Set password for users who signed up with passcode"""

    password: str = Field(
        ..., min_length=8, description="Password must be at least 8 characters"
    )


class RefreshTokenRequest(BaseModel):
    """Request to refresh access token"""

    refresh_token: str


class TokenResponse(BaseModel):
    """Standard token response for all auth endpoints"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict
    requires_password: Optional[bool] = (
        None  # For passcode users who need to set password
    )


class UserInfo(BaseModel):
    """User information included in token responses"""

    id: int
    email: str
    full_name: str
    license_number: Optional[str] = None
    is_verified: bool
    is_premium: bool
