# Updated app/models/user.py or app/models/payment.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    license_number = Column(String, index=True)

    # Password fields (for regular email auth)
    hashed_password = Column(
        String, nullable=True
    )  # Nullable because Google users won't have a password

    # OAuth fields
    auth_provider = Column(String, default="email")  # "email", "google", etc.
    oauth_id = Column(String, nullable=True, index=True)  # Google's unique user ID
    oauth_access_token = Column(Text, nullable=True)
    oauth_refresh_token = Column(Text, nullable=True)
    oauth_token_expires = Column(DateTime(timezone=True), nullable=True)

    # User profile data
    profile_picture = Column(
        String, nullable=True
    )  # URL to profile picture (useful for Google profiles)

    # Additional user data
    metadata = Column(JSON, nullable=True)  # Flexible field for additional data

    # Account status
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', auth_provider='{self.auth_provider}')>"
