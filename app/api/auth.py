# app/api/auth.py - Enhanced logout endpoint with token management
from fastapi import APIRouter, Depends, HTTPException, Body, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import GoogleAuthService
from app.services.jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
)
from app.models.user import User
from app.models.cpa import CPA
from typing import Dict, Any, Optional
from datetime import datetime
import json
from app.services.auth_service import (
    GoogleAuthService,
    authenticate_user,
    get_password_hash,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/google/login")
async def google_login(db: Session = Depends(get_db)):
    """Generate Google OAuth URL for login"""
    auth_service = GoogleAuthService(db)
    oauth_url = auth_service.get_oauth_url()
    return {"auth_url": oauth_url}


@router.get("/google/callback")
async def google_callback(
    code: str, redirect_target: str = None, db: Session = Depends(get_db)
):
    """Handle Google OAuth callback and authenticate user"""
    auth_service = GoogleAuthService(db)

    try:
        user = auth_service.authenticate_google_user(code)

        # Generate tokens
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id}
        )

        # Prepare redirect URL with tokens
        frontend_url = settings.frontend_url

        # FIXED: Always redirect to the auth callback page, not directly to dashboard
        # The frontend AuthCallback component will handle the final routing
        callback_url = f"{frontend_url}/auth/callback"

        # Build query parameters
        params = [f"access_token={access_token}", f"refresh_token={refresh_token}"]

        # Include license number if available (helps with routing decision)
        if user.license_number:
            params.append(f"user_license={user.license_number}")

        # Include user info for better UX
        if user.name:
            # URL encode the name to handle spaces and special characters
            import urllib.parse

            encoded_name = urllib.parse.quote(user.name)
            params.append(f"user_name={encoded_name}")

        redirect_url = f"{callback_url}?{'&'.join(params)}"

        # Add debug logging
        print(
            f"OAuth Success: Redirecting user {user.email} (license: {user.license_number}) to: {redirect_url}"
        )

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        error_msg = str(e)
        print(f"OAuth callback error: {error_msg}")  # Debug log

        # Redirect to frontend with error
        import urllib.parse

        error_redirect = f"{settings.frontend_url}/?error=auth_failed&message={urllib.parse.quote(error_msg)}"
        return RedirectResponse(url=error_redirect)


@router.post("/refresh")
async def refresh_token(data: Dict[str, str] = Body(...)):
    """Refresh access token using refresh token"""
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")

    try:
        # Verify refresh token
        payload = verify_token(refresh_token)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Generate new access token
        new_access_token = create_access_token(
            data={"sub": payload.get("sub"), "user_id": user_id}
        )

        return {"access_token": new_access_token, "token_type": "bearer"}

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "license_number": current_user.license_number,
        "auth_provider": current_user.auth_provider,
        "is_verified": current_user.is_verified,
        "profile_picture": current_user.profile_picture,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
    }


@router.post("/connect-license")
async def connect_license_to_user(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connect CPA license to user account"""
    license_number = data.get("license_number")

    if not license_number:
        raise HTTPException(status_code=400, detail="License number is required")

    # Verify the license exists in our CPA database
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404, detail="CPA license not found in NH database"
        )

    # Check if license is already connected to another user
    existing_user = (
        db.query(User)
        .filter(User.license_number == license_number, User.id != current_user.id)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=409, detail="License already connected to another account"
        )

    # Connect license to current user
    current_user.license_number = license_number
    current_user.updated_at = datetime.now()

    db.commit()
    db.refresh(current_user)

    return {
        "success": True,
        "message": "License connected successfully",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "license_number": current_user.license_number,
        },
        "cpa": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name,
            "status": cpa.status,
        },
    }


@router.post("/signup-with-email")
async def signup_with_email(
    data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
):
    """Create account with email and password"""
    email = data.get("email")
    name = data.get("name")
    license_number = data.get("license_number")

    if not email or not name:
        raise HTTPException(status_code=400, detail="Email and name are required")

    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=409, detail="Account with this email already exists"
        )

    # Verify license if provided
    cpa = None
    if license_number:
        cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
        if not cpa:
            raise HTTPException(
                status_code=404, detail="CPA license not found in NH database"
            )

        # Check if license is already connected
        existing_license_user = (
            db.query(User).filter(User.license_number == license_number).first()
        )
        if existing_license_user:
            raise HTTPException(
                status_code=409, detail="License already connected to another account"
            )

    try:
        # Create new user
        user = User(
            email=email,
            name=name,
            license_number=license_number,
            auth_provider="email",
            is_verified=True,  # For now, skip email verification
            is_active=True,
            created_at=datetime.now(),
            last_login=datetime.now(),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        # Generate tokens
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id}
        )

        return {
            "success": True,
            "message": "Account created successfully",
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "license_number": user.license_number,
                "auth_provider": user.auth_provider,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create account: {str(e)}"
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Enhanced logout that clears OAuth tokens and updates user state"""
    try:
        # Clear OAuth tokens if this was a Google-authenticated user
        if current_user.auth_provider == "google":
            current_user.oauth_access_token = None
            current_user.oauth_refresh_token = None
            current_user.oauth_token_expires = None

        # Update last logout time (you may want to add this field to your User model)
        current_user.updated_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": "Logged out successfully",
            "redirect_url": "/",
        }

    except Exception as e:
        # Even if database update fails, we should still allow logout
        print(f"Logout error (non-critical): {e}")
        return {
            "success": True,
            "message": "Logged out successfully",
            "redirect_url": "/",
        }


# NEW: Endpoint to check if user still exists (useful for debugging)
@router.get("/status")
async def auth_status(current_user: User = Depends(get_current_user)):
    """Get authentication status and user info"""
    return {
        "authenticated": True,
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name,
            "license_number": current_user.license_number,
            "auth_provider": current_user.auth_provider,
            "is_active": current_user.is_active,
            "last_login": current_user.last_login,
        },
    }


# NEW: Admin endpoint to invalidate user tokens (for when deleting users)
@router.post("/invalidate-user-tokens/{user_id}")
async def invalidate_user_tokens(
    user_id: int,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)  # Add admin check here
):
    """
    Invalidate all tokens for a specific user (call this before deleting a user)
    This should be called by admin functions before deleting users from the database
    """

    # TODO: Add admin permission check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Clear all OAuth tokens
        user.oauth_access_token = None
        user.oauth_refresh_token = None
        user.oauth_token_expires = None
        user.is_active = False  # Deactivate user
        user.updated_at = datetime.utcnow()

        db.commit()

        return {
            "success": True,
            "message": f"All tokens invalidated for user {user.email}",
            "user_id": user_id,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to invalidate tokens: {str(e)}"
        )


@router.post("/login")
async def login(data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
    """Login for existing users"""
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Optional: Verify CPA license still active
    if user.license_number:
        cpa = db.query(CPA).filter(CPA.license_number == user.license_number).first()
        if not cpa or cpa.status != "ACTIVE":
            raise HTTPException(status_code=403, detail="CPA license no longer active")

    # Update last login
    user.last_login = datetime.now()
    db.commit()

    access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "license_number": user.license_number,
        },
    }
