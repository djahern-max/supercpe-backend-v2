# app/api/auth.py - Simplified and clean version
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    PasscodeSignupRequest,
    TokenResponse,
    SetPasswordRequest,
    RefreshTokenRequest,
)
from app.services.auth_service import AuthService
from app.services.jwt_service import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Standard email/password login"""
    auth_service = AuthService(db)

    try:
        result = auth_service.authenticate_user(request.email, request.password)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/signup", response_model=TokenResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Create account with email, password, and license verification"""
    auth_service = AuthService(db)

    try:
        result = auth_service.create_user_with_license(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            license_number=request.license_number,
        )
        return result
    except ValueError as e:
        if "already exists" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        elif "not found" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/signup-with-passcode", response_model=TokenResponse)
async def signup_with_passcode(
    request: PasscodeSignupRequest, db: Session = Depends(get_db)
):
    """Create account using CPA passcode (no password required initially)"""
    auth_service = AuthService(db)

    try:
        result = auth_service.create_user_with_passcode(
            email=request.email, full_name=request.full_name, passcode=request.passcode
        )
        return result
    except ValueError as e:
        if "already exists" in str(e) or "already been used" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        elif "Invalid passcode" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/set-password")
async def set_password(
    request: SetPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set password for users who signed up with passcode"""
    auth_service = AuthService(db)

    try:
        auth_service.set_user_password(current_user.id, request.password)
        return {"success": True, "message": "Password set successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/refresh", response_model=dict)
async def refresh_access_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    auth_service = AuthService(None)  # No DB needed for token operations

    try:
        result = auth_service.refresh_access_token(request.refresh_token)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user profile information"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "license_number": current_user.license_number,
        "is_verified": current_user.is_verified,
        "is_premium": current_user.is_premium,
        "trial_uploads_used": current_user.trial_uploads_used,
        "remaining_trial_uploads": current_user.remaining_trial_uploads,
        "requires_password": not bool(current_user.hashed_password),
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
    }


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Logout current user"""
    # In a simple JWT system, logout is mainly client-side
    # But we can update last_logout timestamp if needed
    try:
        from datetime import datetime

        current_user.updated_at = datetime.now()
        db.commit()
        return {"success": True, "message": "Logged out successfully"}
    except Exception:
        # Even if DB update fails, logout should succeed
        return {"success": True, "message": "Logged out successfully"}
