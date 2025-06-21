# app/models/user.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Float,
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
    user_metadata = Column(
        JSON, nullable=True
    )  # Renamed from 'metadata' to avoid SQLAlchemy reserved name

    # Account status
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    accepted_extended_trial = Column(Boolean, default=False, nullable=False, index=True)
    extended_trial_accepted_at = Column(DateTime(timezone=True), nullable=True)
    initial_trial_completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user")
    cpe_records = relationship(
        "CPERecord", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', auth_provider='{self.auth_provider}')>"


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    license_number = Column(String, index=True)

    # Stripe subscription data
    stripe_customer_id = Column(String, index=True)
    stripe_subscription_id = Column(String, unique=True, index=True)
    stripe_price_id = Column(String)

    # Subscription details
    plan_type = Column(String)  # "monthly", "annual"
    amount = Column(Float)  # Amount in USD
    status = Column(String)  # "active", "past_due", "canceled", "unpaid", etc.
    current_period_start = Column(DateTime(timezone=True))
    current_period_end = Column(DateTime(timezone=True))
    cancel_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)

    # Additional subscription data
    subscription_metadata = Column(
        JSON, nullable=True
    )  # Also renamed to avoid potential issues

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status='{self.status}')>"
