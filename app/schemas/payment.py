# app/schemas/payment.py
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from typing import Optional, Dict, Any


class PaymentBase(BaseModel):
    """Base payment schema"""

    cpa_license_number: str = Field(
        ..., max_length=20, description="CPA license number"
    )
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="usd", max_length=3, description="Currency code")
    payment_type: str = Field(
        ..., max_length=50, description="Type of payment (one_time, subscription)"
    )
    product_type: str = Field(
        ..., max_length=100, description="Product being purchased"
    )


class PaymentCreate(PaymentBase):
    """Schema for creating a new payment"""

    stripe_payment_intent_id: Optional[str] = Field(None, max_length=255)
    stripe_customer_id: Optional[str] = Field(None, max_length=255)
    stripe_subscription_id: Optional[str] = Field(None, max_length=255)


class PaymentUpdate(BaseModel):
    """Schema for updating a payment"""

    status: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    stripe_payment_intent_id: Optional[str] = Field(None, max_length=255)
    stripe_customer_id: Optional[str] = Field(None, max_length=255)


class PaymentResponse(PaymentBase):
    """Schema for payment responses"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    stripe_payment_intent_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    status: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


# Stripe-specific schemas
class PaymentIntentRequest(BaseModel):
    """Schema for creating Stripe payment intents"""

    cpa_license_number: str = Field(..., description="CPA license number")
    amount: float = Field(..., gt=0, description="Payment amount in cents")
    product_type: str = Field(..., description="Product being purchased")
    payment_type: str = Field(default="one_time", description="Payment type")


class SubscriptionRequest(BaseModel):
    """Schema for creating Stripe subscriptions"""

    cpa_license_number: str = Field(..., description="CPA license number")
    plan: str = Field(
        ..., description="Subscription plan (premium_annual, basic_monthly)"
    )


class PaymentIntentResponse(BaseModel):
    """Schema for payment intent responses"""

    client_secret: str
    payment_intent_id: str
    amount: float
    currency: str


class SubscriptionResponse(BaseModel):
    """Schema for subscription responses"""

    subscription_id: str
    customer_id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    plan_id: str
    amount: float


class WebhookEvent(BaseModel):
    """Schema for Stripe webhook events"""

    id: str
    type: str
    data: Dict[str, Any]
    created: int


class PricingPlan(BaseModel):
    """Schema for pricing plan information"""

    id: str
    name: str
    price: float
    currency: str
    interval: str
    features: list[str]
    is_popular: bool = False
