# app/api/auth.py
from fastapi import APIRouter, Depends, HTTPException, Body, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.services.auth_service import GoogleAuthService
from app.services.jwt_service import create_access_token, create_refresh_token
from app.models.user import User
from typing import Dict, Any
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
        frontend_url = settings.FRONTEND_URL
        target = redirect_target or "/dashboard"
        redirect_url = f"{frontend_url}{target}?access_token={access_token}&refresh_token={refresh_token}"

        # If user has a license number, add it to the redirect
        if user.license_number:
            redirect_url += f"&license_number={user.license_number}"

        # Redirect to frontend with tokens
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        error_msg = str(e)
        error_redirect = f"{settings.FRONTEND_URL}/auth/error?message={error_msg}"
        return RedirectResponse(url=error_redirect)


@router.post("/connect-license")
async def connect_license_to_user(
    data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
):
    """Connect CPA license to user account"""

    user_id = data.get("user_id")
    license_number = data.get("license_number")

    if not user_id or not license_number:
        raise HTTPException(
            status_code=400, detail="User ID and license number are required"
        )

    # Find user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify license exists in CPA database
    from app.models.cpa import CPA

    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404, detail="CPA license number not found in database"
        )

    # Connect license to user
    user.license_number = license_number
    db.commit()

    return {
        "success": True,
        "message": "License connected successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "license_number": user.license_number,
        },
    }
