# app/services/auth_service.py - Updated with lowercase settings
import requests
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.user import User


class GoogleAuthService:
    def __init__(self, db: Session):
        self.db = db
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.redirect_uri = f"{settings.backend_url}/api/auth/google/callback"

    def get_oauth_url(self):
        """Generate the Google OAuth URL for authorization"""

        auth_url = "https://accounts.google.com/o/oauth2/auth"
        scope = "email profile"

        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
            "access_type": "offline",
            "prompt": "consent",  # Force to get refresh_token
        }

        # Convert params to URL query string
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])

        return f"{auth_url}?{query_string}"

    def exchange_code_for_tokens(self, code):
        """Exchange authorization code for access and refresh tokens"""

        token_url = "https://oauth2.googleapis.com/token"

        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }

        response = requests.post(token_url, data=data)

        if response.status_code != 200:
            raise HTTPException(
                status_code=400, detail="Failed to exchange authorization code"
            )

        tokens = response.json()
        return tokens

    def get_user_info(self, access_token):
        """Get user info from Google using access token"""

        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = requests.get(user_info_url, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get user info")

        user_info = response.json()
        return user_info

    def authenticate_google_user(self, code):
        """Complete Google authentication flow and return or create user"""

        # Exchange code for tokens
        tokens = self.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get(
            "refresh_token"
        )  # May be None if user already granted permission
        expires_in = tokens.get("expires_in", 3600)  # Default to 1 hour

        # Get user info from Google
        user_info = self.get_user_info(access_token)

        # Get user email, Google ID, and name
        email = user_info.get("email")
        google_id = user_info.get("id")
        name = user_info.get("name")
        picture = user_info.get("picture")

        # Check if user exists
        user = self.db.query(User).filter(User.email == email).first()

        if not user:
            # Create new user
            user = User(
                email=email,
                name=name,
                auth_provider="google",
                oauth_id=google_id,
                oauth_access_token=access_token,
                oauth_refresh_token=refresh_token,
                oauth_token_expires=datetime.now() + timedelta(seconds=expires_in),
                profile_picture=picture,
                is_verified=True,  # Google accounts are pre-verified
                last_login=datetime.now(),
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        else:
            # Update existing user
            user.oauth_id = google_id
            user.oauth_access_token = access_token
            if refresh_token:
                user.oauth_refresh_token = refresh_token
            user.oauth_token_expires = datetime.now() + timedelta(seconds=expires_in)
            user.last_login = datetime.now()
            user.auth_provider = "google"
            user.is_verified = True
            user.profile_picture = picture

            self.db.commit()
            self.db.refresh(user)

        return user
