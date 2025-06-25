# app/schemas/auth.py - Complete auth schemas with all required imports
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


class OAuthLoginRequest(BaseModel):
    """OAuth login request (placeholder for future OAuth implementation)"""

    provider: str = Field(..., description="OAuth provider (google, microsoft, etc.)")
    access_token: str = Field(..., description="OAuth access token")


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


class TokenRefreshRequest(BaseModel):
    """Alternative name for refresh token request"""

    refresh_token: str


class PasswordResetRequest(BaseModel):
    """Request to reset password"""

    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token"""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")


class EmailVerificationRequest(BaseModel):
    """Request to verify email"""

    token: str = Field(..., description="Email verification token")


class ChangePasswordRequest(BaseModel):
    """Request to change password (when logged in)"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")


class LicenseVerificationRequest(BaseModel):
    """Request to verify CPA license"""

    license_number: str = Field(..., max_length=20, description="CPA license number")
    last_name: str = Field(..., max_length=100, description="Last name on license")


class LicenseVerificationResponse(BaseModel):
    """Response for license verification"""

    is_valid: bool
    license_number: str
    full_name: Optional[str] = None
    expiration_date: Optional[str] = None
    status: Optional[str] = None
    message: str


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
