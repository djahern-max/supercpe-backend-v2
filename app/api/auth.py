# app/api/auth.py - Simplified version without OAuth
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.cpa import CPA
from app.services.jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
)
from app.models.user import User
from typing import Dict, Any
from datetime import datetime
from app.services.auth_service import (
    authenticate_user,
    get_password_hash,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


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
        if not cpa or cpa.status.upper() != "ACTIVE":
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
            "full_name": user.full_name,
            "license_number": user.license_number,
        },
    }


@router.post("/signup-with-email")
async def signup_with_email(
    data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
):
    """Create account with email and password"""
    email = data.get("email")
    full_name = data.get("full_name") or data.get("name")
    password = data.get("password")
    license_number = data.get("license_number")

    if not email or not full_name or not password:
        raise HTTPException(
            status_code=400, detail="Email, name, and password are required"
        )

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
            full_name=full_name,
            license_number=license_number,
            hashed_password=get_password_hash(password),
            is_verified=True,
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
                "full_name": user.full_name,
                "license_number": user.license_number,
            },
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create account: {str(e)}"
        )


@router.post("/signup-with-passcode")
async def signup_with_passcode(
    data: Dict[str, Any] = Body(...), db: Session = Depends(get_db)
):
    """Create account using passcode verification"""
    email = data.get("email")
    full_name = data.get("full_name") or data.get("name")
    passcode = data.get("passcode")

    if not email or not full_name or not passcode:
        raise HTTPException(
            status_code=400, detail="Email, name, and passcode are required"
        )

    # Verify the passcode and get CPA info
    cpa = db.query(CPA).filter(CPA.passcode == passcode).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="Invalid passcode")

    # Check if user already exists with this email
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=409, detail="Account with this email already exists"
        )

    # Check if license is already connected to another user
    existing_license_user = (
        db.query(User).filter(User.license_number == cpa.license_number).first()
    )
    if existing_license_user:
        raise HTTPException(
            status_code=409, detail="This passcode has already been used"
        )

    try:
        # Generate a secure temporary password
        import secrets
        import string

        temp_password = "".join(
            secrets.choice(string.ascii_letters + string.digits + "!@#$%")
            for _ in range(16)
        )

        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            license_number=cpa.license_number,
            hashed_password=get_password_hash(temp_password),
            is_verified=True,
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
                "full_name": user.full_name,
                "license_number": user.license_number,
            },
            "temporary_password": temp_password,
            "requires_password_reset": True,
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create account: {str(e)}"
        )


@router.post("/set-password")
async def set_password(
    data: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow users to set their own password"""
    new_password = data.get("password")

    if not new_password:
        raise HTTPException(status_code=400, detail="Password is required")

    if len(new_password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )

    try:
        current_user.hashed_password = get_password_hash(new_password)
        current_user.updated_at = datetime.now()
        db.commit()

        return {"success": True, "message": "Password set successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set password: {str(e)}")


@router.get("/me")
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "license_number": current_user.license_number,
        "is_verified": current_user.is_verified,
        "is_premium": current_user.is_premium,
        "trial_uploads_used": current_user.trial_uploads_used,
        "remaining_trial_uploads": current_user.remaining_trial_uploads,
        "created_at": current_user.created_at,
        "last_login": current_user.last_login,
    }


@router.post("/refresh")
async def refresh_token(data: Dict[str, str] = Body(...)):
    """Refresh access token using refresh token"""
    refresh_token = data.get("refresh_token")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Refresh token required")

    try:
        payload = verify_token(refresh_token)
        user_id = payload.get("user_id")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_access_token(
            data={"sub": payload.get("sub"), "user_id": user_id}
        )

        return {"access_token": new_access_token, "token_type": "bearer"}

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Logout user"""
    try:
        current_user.updated_at = datetime.now()
        db.commit()

        return {"success": True, "message": "Logged out successfully"}

    except Exception as e:
        return {"success": True, "message": "Logged out successfully"}


@router.put("/admin/set-passcode/{license_number}")
async def set_passcode_for_testing(
    license_number: str, passcode: str, db: Session = Depends(get_db)
):
    """Admin endpoint to set passcode for testing"""
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()

    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    cpa.passcode = passcode
    db.commit()
    db.refresh(cpa)

    return {
        "success": True,
        "message": f"Passcode set for {cpa.full_name}",
        "cpa": {
            "license_number": cpa.license_number,
            "full_name": cpa.full_name,
            "passcode": cpa.passcode,
            "status": cpa.status,
        },
    }
