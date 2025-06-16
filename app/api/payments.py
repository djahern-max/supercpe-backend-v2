from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.stripe_service import StripeService
from app.models.cpa import CPA
from app.models.payment import Payment, CPASubscription
from pydantic import BaseModel
from typing import Dict, Any
import stripe

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
    request: PaymentIntentRequest,
    db: Session = Depends(get_db)
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
        payment_type=request.payment_type
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return result

@router.get("/subscription-status/{license_number}")
async def get_subscription_status(
    license_number: str,
    db: Session = Depends(get_db)
):
    """Check if CPA has active subscription"""
    
    stripe_service = StripeService(db)
    has_subscription = stripe_service.has_active_subscription(license_number)
    
    # Get subscription details
    subscription = db.query(CPASubscription).filter(
        CPASubscription.cpa_license_number == license_number,
        CPASubscription.is_active == True
    ).first()
    
    return {
        "has_active_subscription": has_subscription,
        "subscription": {
            "type": subscription.subscription_type if subscription else None,
            "expires_at": subscription.expires_at if subscription else None,
            "features": {
                "document_uploads": subscription.document_uploads_allowed if subscription else False,
                "ai_parsing": subscription.ai_parsing_enabled if subscription else False,
                "advanced_reports": subscription.advanced_reports if subscription else False
            }
        } if subscription else None
    }

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhooks"""
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        
        # Update payment status
        stripe_service = StripeService(db)
        stripe_service.check_payment_status(payment_intent['id'])
        
    elif event['type'] == 'invoice.payment_succeeded':
        # Handle subscription payment
        invoice = event['data']['object']
        # Process subscription payment...
        
    return {"status": "success"}
