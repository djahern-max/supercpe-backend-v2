# app/api/auth.py - Enhanced Authentication Endpoints
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

        # CHANGE: Default to reporting requirements instead of generic dashboard
        if user.license_number:
            # User has license - go to their dashboard with reporting tab
            target = f"/dashboard/{user.license_number}?tab=reporting"
        else:
            # No license - go to general reporting requirements page
            target = redirect_target or "/reporting-requirements"

        redirect_url = f"{frontend_url}{target}?access_token={access_token}&refresh_token={refresh_token}"

        return RedirectResponse(url=redirect_url)

    except Exception as e:
        error_msg = str(e)
        error_redirect = f"{settings.frontend_url}/auth/error?message={error_msg}"
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
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user (client should clear tokens)"""
    return {"success": True, "message": "Logged out successfully"}
