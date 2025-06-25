# app/schemas/__init__.py
"""
Pydantic schemas for FastAPI request/response validation

This module contains all the Pydantic models used for:
- Request validation
- Response serialization
- API documentation
"""

# CPE Record schemas
from .cpe_record import (
    CPERecordBase,
    CPERecordCreate,
    CPERecordUpdate,
    CPERecordResponse,
    CPERecordListResponse,
    LegacyCPERecordResponse,
)

# User schemas
from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserProfileResponse,
    UserAuthResponse,
    PasswordUpdate,
    PasswordReset,
    PasswordResetConfirm,
)

# CPA schemas
from .cpa import (
    CPABase,
    CPACreate,
    CPAUpdate,
    CPAResponse,
    CPAListResponse,
    CPASearchResult,
)

# Payment schemas
from .payment import (
    PaymentBase,
    PaymentCreate,
    PaymentUpdate,
    PaymentResponse,
    PaymentIntentRequest,
    SubscriptionRequest,
    PaymentIntentResponse,
    SubscriptionResponse,
    WebhookEvent,
    PricingPlan,
)

# Auth schemas
from .auth import (
    LoginRequest,
    SignupRequest,
    OAuthLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    EmailVerificationRequest,
    ChangePasswordRequest,
    LicenseVerificationRequest,
    LicenseVerificationResponse,
)

__all__ = [
    # CPE Record
    "CPERecordBase",
    "CPERecordCreate",
    "CPERecordUpdate",
    "CPERecordResponse",
    "CPERecordListResponse",
    "LegacyCPERecordResponse",
    # User
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserProfileResponse",
    "UserAuthResponse",
    "PasswordUpdate",
    "PasswordReset",
    "PasswordResetConfirm",
    # CPA
    "CPABase",
    "CPACreate",
    "CPAUpdate",
    "CPAResponse",
    "CPAListResponse",
    "CPASearchResult",
    # Payment
    "PaymentBase",
    "PaymentCreate",
    "PaymentUpdate",
    "PaymentResponse",
    "PaymentIntentRequest",
    "SubscriptionRequest",
    "PaymentIntentResponse",
    "SubscriptionResponse",
    "WebhookEvent",
    "PricingPlan",
    # Auth
    "LoginRequest",
    "SignupRequest",
    "OAuthLoginRequest",
    "TokenResponse",
    "TokenRefreshRequest",
    "PasswordResetRequest",
    "PasswordResetConfirm",
    "EmailVerificationRequest",
    "ChangePasswordRequest",
    "LicenseVerificationRequest",
    "LicenseVerificationResponse",
]
