# app/models/user.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Basic user info
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False)
    license_number = Column(String(20), index=True, nullable=False)

    # Authentication
    hashed_password = Column(String(255), nullable=False)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_login = Column(DateTime, nullable=True)

    # Trial/subscription tracking
    trial_uploads_used = Column(Integer, default=0, nullable=False)
    is_premium = Column(Boolean, default=False, nullable=False)

    # ===== FIXED RELATIONSHIPS with explicit foreign_keys =====
    cpe_records = relationship(
        "CPERecord", foreign_keys="CPERecord.user_id", back_populates="user"
    )
    subscriptions = relationship("Subscription", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', license='{self.license_number}')>"

    @property
    def remaining_trial_uploads(self):
        """Calculate remaining trial uploads"""
        max_trial_uploads = 10  # or whatever your limit is
        return max(0, max_trial_uploads - self.trial_uploads_used)

    @property
    def can_upload(self):
        """Check if user can upload more files"""
        return self.is_premium or self.remaining_trial_uploads > 0


class Subscription(Base):
    __tablename__ = "subscriptions"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Stripe subscription data
    stripe_customer_id = Column(String(255), index=True)
    stripe_subscription_id = Column(String(255), unique=True, index=True)
    stripe_price_id = Column(String(255))

    # Subscription details
    plan_type = Column(String(50), nullable=False)  # "monthly", "annual"
    amount = Column(Float, nullable=False)  # Amount in USD
    status = Column(
        String(50), nullable=False
    )  # "active", "past_due", "canceled", etc.

    # Billing periods
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    cancel_at = Column(DateTime, nullable=True)
    canceled_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

    @property
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in ["active", "trialing"]
