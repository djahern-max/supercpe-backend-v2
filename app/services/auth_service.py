# app/services/auth_service.py - Centralized authentication logic
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.cpa import CPA
from app.services.jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
)
from passlib.context import CryptContext
from datetime import datetime
from typing import Dict, Any
import secrets
import string


# Create password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate_user(self, email: str, password: str) -> Dict[str, Any]:
        """Authenticate user with email and password"""
        # Find user
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("Invalid email or password")

        # Verify password
        if not user.hashed_password or not verify_password(
            password, user.hashed_password
        ):
            raise ValueError("Invalid email or password")

        # Check if user is active
        if not user.is_active:
            raise ValueError("Account is inactive")

        # Verify CPA license is still active (if user has one)
        if user.license_number:
            cpa = (
                self.db.query(CPA)
                .filter(CPA.license_number == user.license_number)
                .first()
            )
            if not cpa or cpa.status.upper() != "ACTIVE":
                raise ValueError("CPA license is no longer active")

        # Update last login
        user.last_login = datetime.now()
        self.db.commit()

        return self._create_token_response(user)

    def create_user_with_license(
        self, email: str, password: str, full_name: str, license_number: str
    ) -> Dict[str, Any]:
        """Create user account with license verification"""
        # Check if user already exists
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Account with this email already exists")

        # Verify CPA license exists and is active
        cpa = self.db.query(CPA).filter(CPA.license_number == license_number).first()
        if not cpa:
            raise ValueError("CPA license not found in NH database")

        if cpa.status.upper() != "ACTIVE":
            raise ValueError("CPA license is not active")

        # Check if license is already connected to another user
        if self.db.query(User).filter(User.license_number == license_number).first():
            raise ValueError("License already connected to another account")

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

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return self._create_token_response(user)

    def create_user_with_passcode(
        self, email: str, full_name: str, passcode: str
    ) -> Dict[str, Any]:
        """Create user account using CPA passcode"""
        # Check if user already exists
        if self.db.query(User).filter(User.email == email).first():
            raise ValueError("Account with this email already exists")

        # Verify passcode and get CPA info
        cpa = self.db.query(CPA).filter(CPA.passcode == passcode).first()
        if not cpa:
            raise ValueError("Invalid passcode")

        # Check if license is already connected to another user
        if (
            self.db.query(User)
            .filter(User.license_number == cpa.license_number)
            .first()
        ):
            raise ValueError("This passcode has already been used")

        # Create user without password (they'll set it later)
        user = User(
            email=email,
            full_name=full_name,
            license_number=cpa.license_number,
            hashed_password=None,  # No password yet
            is_verified=True,
            is_active=True,
            created_at=datetime.now(),
            last_login=datetime.now(),
        )

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        # Create response with flag indicating password is required
        response = self._create_token_response(user)
        response["requires_password"] = True
        return response

    def set_user_password(self, user_id: int, password: str) -> None:
        """Set password for a user (typically after passcode signup)"""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        user.hashed_password = get_password_hash(password)
        user.updated_at = datetime.now()
        self.db.commit()

    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """Create new access token from refresh token"""
        try:
            payload = verify_token(refresh_token)
            user_id = payload.get("user_id")
            email = payload.get("sub")

            if not user_id or not email:
                raise ValueError("Invalid refresh token")

            new_access_token = create_access_token(
                data={"sub": email, "user_id": user_id}
            )

            return {"access_token": new_access_token, "token_type": "bearer"}

        except Exception:
            raise ValueError("Invalid refresh token")

    def _create_token_response(self, user: User) -> Dict[str, Any]:
        """Create standardized token response"""
        access_token = create_access_token(data={"sub": user.email, "user_id": user.id})
        refresh_token = create_refresh_token(
            data={"sub": user.email, "user_id": user.id}
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600,  # 1 hour
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "license_number": user.license_number,
                "is_verified": user.is_verified,
                "is_premium": user.is_premium,
            },
        }
