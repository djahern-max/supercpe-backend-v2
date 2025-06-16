from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Payment(Base):
    __tablename__ = "payments"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # CPA association
    cpa_license_number = Column(String(20), nullable=False, index=True)

    # Stripe data
    stripe_payment_intent_id = Column(String(255), unique=True, index=True)
    stripe_customer_id = Column(String(255), index=True)
    stripe_subscription_id = Column(String(255), index=True, nullable=True)

    # Payment details
    amount = Column(Float, nullable=False)  # Amount in dollars
    currency = Column(String(3), default="USD")
    payment_type = Column(
        String(50), nullable=False
    )  # "one_time", "subscription", "license_annual"
    product_type = Column(
        String(100), nullable=False
    )  # "document_upload", "premium_annual", "basic_monthly"

    # Status
    status = Column(
        String(50), default="pending"
    )  # pending, succeeded, failed, canceled
    is_active = Column(Boolean, default=True)

    # Dates
    payment_date = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(
        DateTime(timezone=True), nullable=True
    )  # For subscriptions/annual
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Metadata
    payment_metadata = Column(Text, nullable=True)  # JSON string for flexible data

    def __repr__(self):
        return f"<Payment(license={self.cpa_license_number}, amount=${self.amount}, type={self.payment_type})>"


class CPASubscription(Base):
    __tablename__ = "cpa_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    cpa_license_number = Column(String(20), nullable=False, index=True)

    # Subscription details
    subscription_type = Column(
        String(50), nullable=False
    )  # "basic", "premium", "enterprise"
    is_active = Column(Boolean, default=True)

    # Features enabled
    document_uploads_allowed = Column(Boolean, default=False)
    ai_parsing_enabled = Column(Boolean, default=False)
    advanced_reports = Column(Boolean, default=False)
    api_access = Column(Boolean, default=False)

    # Dates
    starts_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<CPASubscription(license={self.cpa_license_number}, type={self.subscription_type})>"
