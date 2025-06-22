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
    """Handle Stripe webhooks with enhanced logging"""
    body = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Log incoming webhook
    print(f"=== WEBHOOK RECEIVED ===")
    print(f"Headers: {dict(request.headers)}")
    print(f"Body length: {len(body)}")

    try:
        # TEMP: Skip signature verification for testing
        import json

        event = json.loads(body.decode("utf-8"))

        print(f"Event Type: {event.get('type')}")
        print(f"Event ID: {event.get('id')}")
        print(f"Event Data Keys: {list(event.get('data', {}).keys())}")

    except ValueError as e:
        print(f"Invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    # Handle the event
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        print(f"=== PROCESSING CHECKOUT SESSION ===")
        print(f"Session ID: {session['id']}")
        print(f"Customer: {session.get('customer')}")
        print(f"Subscription: {session.get('subscription')}")
        print(f"Metadata: {session.get('metadata', {})}")
        print(f"Customer Details: {session.get('customer_details', {})}")

        # Process the successful payment
        stripe_service = StripeService(db)
        try:
            result = stripe_service.handle_successful_payment(session["id"])
            print(f"Payment processing result: {result}")
            print("=== PAYMENT PROCESSED SUCCESSFULLY ===")

            # IMPORTANT: Commit the transaction
            db.commit()
            print("Database transaction committed")

        except Exception as e:
            print(f"=== PAYMENT PROCESSING ERROR ===")
            print(f"Error: {e}")
            print(f"Error type: {type(e)}")
            import traceback

            traceback.print_exc()

            # Rollback transaction on error
            db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Payment processing error: {str(e)}"
            )

    elif event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        print(f"Processing invoice payment: {invoice['id']}")
        # Process subscription payment...

    else:
        print(f"Unhandled event type: {event['type']}")

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


@router.post("/test-webhook")
async def test_webhook_processing(
    data: dict = Body(...), db: Session = Depends(get_db)
):
    """Manual endpoint to test webhook processing with a session ID"""
    session_id = data.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    stripe_service = StripeService(db)
    try:
        result = stripe_service.handle_successful_payment(session_id)
        db.commit()  # Important: commit the transaction
        return {"success": True, "result": result}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
