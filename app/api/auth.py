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


# Add this temporarily to your app/api/auth.py for debugging


@router.post("/signup-with-passcode", response_model=TokenResponse)
async def signup_with_passcode(
    request: PasscodeSignupRequest, db: Session = Depends(get_db)
):
    """Create account using CPA passcode (no password required initially)"""
    import traceback
    import logging

    logger = logging.getLogger(__name__)

    try:
        logger.info(f"🔍 DEBUG: Starting passcode signup for {request.email}")

        # Check if secret key exists
        from app.core.config import settings

        if (
            not settings.secret_key
            or settings.secret_key == "your-secret-key-change-in-production"
        ):
            logger.error("❌ SECRET_KEY not properly configured")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server configuration error: SECRET_KEY not set",
            )

        logger.info("✅ SECRET_KEY configured")

        # Test database connection
        try:
            db.execute("SELECT 1")
            logger.info("✅ Database connection working")
        except Exception as db_error:
            logger.error(f"❌ Database error: {str(db_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database connection error: {str(db_error)}",
            )

        # Initialize auth service
        logger.info("🔍 Initializing AuthService")
        auth_service = AuthService(db)

        # Attempt user creation
        logger.info(f"🔍 Creating user with passcode for {request.email}")
        result = auth_service.create_user_with_passcode(
            email=request.email, full_name=request.full_name, passcode=request.passcode
        )

        logger.info("✅ User created successfully")
        return result

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        logger.error(f"❌ ValueError in signup: {str(e)}")
        if "already exists" in str(e) or "already been used" in str(e):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
        elif "Invalid passcode" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Catch-all for unexpected errors
        logger.error(f"❌ UNEXPECTED ERROR in signup: {str(e)}")
        logger.error(f"❌ TRACEBACK: {traceback.format_exc()}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )
