import stripe
from app.core.config import settings
from app.models.payment import Payment, CPASubscription
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)

# Configure Stripe
stripe.api_key = settings.stripe_secret_key


class StripeService:
    def __init__(self, db: Session):
        self.db = db

    def create_payment_intent(
        self,
        cpa_license_number: str,
        amount: float,
        product_type: str,
        payment_type: str = "one_time",
        metadata: dict = None,
    ) -> dict:
        """Create a Stripe Payment Intent"""
        try:
            # Create payment intent
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency="usd",
                metadata={
                    "cpa_license_number": cpa_license_number,
                    "product_type": product_type,
                    "payment_type": payment_type,
                    **(metadata or {}),
                },
            )

            # Save to database
            payment = Payment(
                cpa_license_number=cpa_license_number,
                stripe_payment_intent_id=intent.id,
                amount=amount,
                payment_type=payment_type,
                product_type=product_type,
                status="pending",
                payment_metadata=json.dumps(metadata) if metadata else None,
            )
            self.db.add(payment)
            self.db.commit()

            return {
                "success": True,
                "client_secret": intent.client_secret,
                "payment_intent_id": intent.id,
                "amount": amount,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error: {e}")
            return {"success": False, "error": str(e)}

    def create_subscription(
        self, cpa_license_number: str, price_id: str, subscription_type: str = "premium"
    ) -> dict:
        """Create a Stripe Subscription"""
        try:
            # Create customer
            customer = stripe.Customer.create(
                metadata={"cpa_license_number": cpa_license_number}
            )

            # Create subscription
            subscription = stripe.Subscription.create(
                customer=customer.id,
                items=[{"price": price_id}],
                metadata={
                    "cpa_license_number": cpa_license_number,
                    "subscription_type": subscription_type,
                },
            )

            return {
                "success": True,
                "subscription_id": subscription.id,
                "customer_id": customer.id,
                "status": subscription.status,
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe subscription error: {e}")
            return {"success": False, "error": str(e)}

    def check_payment_status(self, payment_intent_id: str) -> dict:
        """Check payment status"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            # Update database
            payment = (
                self.db.query(Payment)
                .filter(Payment.stripe_payment_intent_id == payment_intent_id)
                .first()
            )

            if payment:
                payment.status = intent.status
                if intent.status == "succeeded":
                    payment.payment_date = datetime.now()
                    payment.is_active = True

                    # Activate subscription if needed
                    self._activate_cpa_subscription(payment)

                self.db.commit()

            return {"success": True, "status": intent.status, "payment": payment}

        except stripe.error.StripeError as e:
            return {"success": False, "error": str(e)}

    def _activate_cpa_subscription(self, payment: Payment):
        """Activate CPA subscription based on payment"""
        if payment.payment_type == "license_annual":
            # Create/update annual subscription
            subscription = CPASubscription(
                cpa_license_number=payment.cpa_license_number,
                subscription_type="premium",
                document_uploads_allowed=True,
                ai_parsing_enabled=True,
                advanced_reports=True,
                starts_at=datetime.now(),
                expires_at=datetime.now() + timedelta(days=365),
            )
            self.db.add(subscription)

    def has_active_subscription(self, cpa_license_number: str) -> bool:
        """Check if CPA has active subscription"""
        subscription = (
            self.db.query(CPASubscription)
            .filter(
                CPASubscription.cpa_license_number == cpa_license_number,
                CPASubscription.is_active == True,
                CPASubscription.expires_at > datetime.now(),
            )
            .first()
        )

        return subscription is not None

    def get_pricing_plans(self) -> dict:
        """Get available pricing plans"""
        return {
            "free": {
                "name": "Free",
                "price": 0,
                "features": [
                    "Compliance status lookup",
                    "Basic compliance tracking",
                    "License verification",
                ],
            },
            "premium_annual": {
                "name": "Premium Annual",
                "price": 29.00,
                "features": [
                    "Document upload & storage",
                    "AI-powered CPE parsing",
                    "Advanced compliance reports",
                    "Email reminders",
                    "Export capabilities",
                ],
            },
            "pay_per_upload": {
                "name": "Pay Per Upload",
                "price": 2.99,
                "features": [
                    "Single document upload",
                    "AI parsing for that document",
                    "Updated compliance status",
                ],
            },
        }
