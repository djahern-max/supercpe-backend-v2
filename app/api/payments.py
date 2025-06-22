from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.payment import Payment
from app.models.user import Subscription
from pydantic import BaseModel
from typing import Dict, Any
import stripe
from app.core.config import settings
from app.models.user import User
from datetime import datetime
from app.services.jwt_service import get_current_user


router = APIRouter(prefix="/api/payments", tags=["Payments"])


class PaymentIntentRequest(BaseModel):
    cpa_license_number: str
    amount: float
    product_type: str
    payment_type: str = "one_time"


class SubscriptionRequest(BaseModel):
    cpa_license_number: str
    plan: str  # "premium_annual", "basic_monthly"


@router.get("/pricing")
async def get_pricing_plans():
    """Get available pricing plans"""
    stripe_service = StripeService(None)
    return stripe_service.get_pricing_plans()


@router.post("/create-payment-intent")
async def create_payment_intent(
    request: PaymentIntentRequest, db: Session = Depends(get_db)
):
    """Create a payment intent for one-time payments"""

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == request.cpa_license_number).first()
    if not cpa:
        raise HTTPException(status_code=404, detail="CPA not found")

    stripe_service = StripeService(db)
    result = stripe_service.create_payment_intent(
        cpa_license_number=request.cpa_license_number,
        amount=request.amount,
        product_type=request.product_type,
        payment_type=request.payment_type,
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


@router.get("/subscription-status/{license_number}")
async def get_subscription_status(license_number: str, db: Session = Depends(get_db)):
    """Check if CPA has active subscription"""

    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)

    # Get subscription details
    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.cpa_license_number == license_number,
            Subscription.is_active == True,
        )
        .first()
    )

    return {
        "has_active_subscription": has_subscription,
        "subscription": (
            {
                "type": subscription.subscription_type if subscription else None,
                "expires_at": subscription.expires_at if subscription else None,
                "features": {
                    "document_uploads": (
                        subscription.document_uploads_allowed if subscription else False
                    ),
                    "ai_parsing": (
                        subscription.ai_parsing_enabled if subscription else False
                    ),
                    "advanced_reports": (
                        subscription.advanced_reports if subscription else False
                    ),
                },
            }
            if subscription
            else None
        ),
    }


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks"""

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]

        # Update payment status
        stripe_service = StripeService(db)
        stripe_service.check_payment_status(payment_intent["id"])

    elif event["type"] == "invoice.payment_succeeded":
        # Handle subscription payment
        invoice = event["data"]["object"]
        # Process subscription payment...

    return {"status": "success"}


@router.post("/create-account-and-subscription")
async def create_account_and_subscription(
    data: dict = Body(...), db: Session = Depends(get_db)
):
    """Create a NEW user account and initiate payment process (for anonymous users)"""

    # Extract data
    email = data.get("email")
    license_number = data.get("license_number")
    name = data.get("name")
    plan = data.get("plan", "annual")

    if not email or not license_number:
        raise HTTPException(
            status_code=400, detail="Email and license number are required"
        )

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404, detail="CPA license number not found in NH database"
        )

    # Check if user account already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists. Please log in instead.",
        )

    # Create new user account
    user = User(
        email=email,
        name=name or cpa.full_name,
        license_number=license_number,
        auth_provider="email",
        is_verified=False,  # Will be verified after payment
        created_at=datetime.now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Define product details based on plan
    if plan == "monthly":
        price_id = settings.stripe_price_id_monthly
        product_name = "SuperCPE Professional Monthly"
        unit_amount = 1000
        recurring = {"interval": "month"}
    else:
        price_id = settings.stripe_price_id_annual
        product_name = "SuperCPE Professional Annual"
        unit_amount = 9600
        recurring = {"interval": "year"}

    # Create Stripe checkout session
    stripe_service = StripeService(db)
    checkout_session = stripe_service.create_checkout_session(
        customer_email=email,
        license_number=license_number,
        price_id=price_id,
        product_name=product_name,
        unit_amount=unit_amount,
        recurring=recurring,
        success_url=f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/dashboard/{license_number}?payment_cancelled=true",
        metadata={
            "license_number": license_number,
            "plan_type": plan,
            "user_id": user.id,
            "new_account": True,  # Flag to indicate this was a new account creation
        },
    )

    return {
        "success": True,
        "message": "Account created successfully",
        "redirect_url": checkout_session.url,
        "session_id": checkout_session.id,
        "plan": plan,
        "new_account": True,
    }


@router.post("/create-subscription-authenticated")
async def create_subscription_authenticated(
    data: dict = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create subscription for EXISTING authenticated user"""

    license_number = data.get("license_number")
    plan = data.get("plan", "annual")

    if not license_number:
        raise HTTPException(status_code=400, detail="License number is required")

    # Verify user owns this license
    if current_user.license_number != license_number:
        raise HTTPException(
            status_code=403,
            detail="You can only create subscriptions for your own license number",
        )

    # Verify CPA exists
    cpa = db.query(CPA).filter(CPA.license_number == license_number).first()
    if not cpa:
        raise HTTPException(
            status_code=404, detail="CPA license number not found in NH database"
        )

    # Check if user already has an active subscription
    stripe_service = StripeService(db)
    existing_subscription = stripe_service.has_active_subscription(license_number)
    if existing_subscription:
        raise HTTPException(
            status_code=400, detail="You already have an active subscription"
        )

    # Define product details based on plan
    if plan == "monthly":
        price_id = settings.stripe_price_id_monthly
        product_name = "SuperCPE Professional Monthly"
        unit_amount = 1000
        recurring = {"interval": "month"}
    else:
        price_id = settings.stripe_price_id_annual
        product_name = "SuperCPE Professional Annual"
        unit_amount = 9600
        recurring = {"interval": "year"}

    # Create Stripe checkout session using existing user data
    checkout_session = stripe_service.create_checkout_session(
        customer_email=current_user.email,
        license_number=license_number,
        price_id=price_id,
        product_name=product_name,
        unit_amount=unit_amount,
        recurring=recurring,
        success_url=f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.frontend_url}/dashboard/{license_number}?payment_cancelled=true",
        metadata={
            "license_number": license_number,
            "plan_type": plan,
            "user_id": current_user.id,
            "authenticated_user": True,
        },
    )

    return {
        "success": True,
        "message": "Subscription created successfully",
        "redirect_url": checkout_session.url,
        "session_id": checkout_session.id,
        "plan": plan,
        "existing_user": True,
    }
