# app/services/stripe_service.py - FIXED VERSION
import stripe
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.payment import Payment
from app.models.user import User, Subscription
from app.models.cpa import CPA
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class StripeService:
    def __init__(self, db: Session):
        self.db = db
        stripe.api_key = settings.stripe_secret_key

    def has_active_subscription(self, license_number: str) -> bool:
        """Check if CPA has active subscription - FIXED to use correct field name"""
        try:
            # FIXED: Use license_number instead of cpa_license_number
            subscription = (
                self.db.query(Subscription)
                .filter(
                    Subscription.license_number
                    == license_number,  # FIXED: correct field name
                    Subscription.status == "active",
                    Subscription.current_period_end > datetime.now(),
                )
                .first()
            )

            if subscription:
                # Verify with Stripe to ensure it's still active
                try:
                    stripe_subscription = stripe.Subscription.retrieve(
                        subscription.stripe_subscription_id
                    )

                    if stripe_subscription.status in ["active", "trialing"]:
                        return True
                    else:
                        # Update local status if Stripe shows different
                        subscription.status = stripe_subscription.status
                        self.db.commit()
                        return False

                except stripe.error.StripeError:
                    # If Stripe call fails, rely on local data for now
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking subscription status: {e}")
            return False

    def get_subscription_status(self, license_number: str):
        """Get detailed subscription status - FIXED"""
        try:
            # FIXED: Use correct field name
            subscription = (
                self.db.query(Subscription)
                .filter(Subscription.license_number == license_number)  # FIXED
                .first()
            )

            if not subscription:
                return {
                    "has_subscription": False,
                    "status": "none",
                    "message": "No subscription found",
                }

            # Get fresh data from Stripe
            try:
                stripe_subscription = stripe.Subscription.retrieve(
                    subscription.stripe_subscription_id
                )

                # Update local record
                subscription.status = stripe_subscription.status
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_subscription.current_period_start
                )
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription.current_period_end
                )
                self.db.commit()

                return {
                    "has_subscription": stripe_subscription.status
                    in ["active", "trialing"],
                    "status": stripe_subscription.status,
                    "current_period_end": subscription.current_period_end.isoformat(),
                    "current_period_start": subscription.current_period_start.isoformat(),
                    "plan_name": self._get_plan_name_from_subscription(
                        stripe_subscription
                    ),
                    "cancel_at_period_end": stripe_subscription.cancel_at_period_end,
                    "next_payment_date": (
                        subscription.current_period_end.isoformat()
                        if not stripe_subscription.cancel_at_period_end
                        else None
                    ),
                }

            except stripe.error.StripeError as e:
                logger.error(f"Error fetching Stripe subscription: {e}")
                # Return local data as fallback
                return {
                    "has_subscription": subscription.status == "active",
                    "status": subscription.status,
                    "current_period_end": subscription.current_period_end.isoformat(),
                    "message": "Using cached subscription data",
                }

        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return {
                "has_subscription": False,
                "status": "error",
                "message": "Error checking subscription status",
            }

    def create_checkout_session(
        self,
        customer_email: str,
        license_number: str,
        price_id: str = None,
        product_name: str = "SuperCPE Professional",
        unit_amount: int = 1000,  # $10 in cents
        recurring: dict = {"interval": "month"},
        success_url: str = None,
        cancel_url: str = None,
        metadata: dict = None,
    ):
        """Create a Stripe checkout session for subscription"""
        try:
            # Create or retrieve customer
            customer = self._get_or_create_customer(customer_email, license_number)

            # Prepare line items
            if price_id and price_id.startswith("price_"):
                # Use existing Stripe price (now with real Price IDs)
                line_items = [
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ]
            else:
                # Fallback to dynamic pricing if no valid price_id
                line_items = [
                    {
                        "price_data": {
                            "currency": "usd",
                            "product_data": {
                                "name": product_name,
                                "description": f"Professional CPE management for NH CPA #{license_number}",
                            },
                            "unit_amount": unit_amount,
                            "recurring": recurring,
                        },
                        "quantity": 1,
                    }
                ]

            # Create checkout session
            checkout_session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=["card"],
                line_items=line_items,
                mode="subscription",
                success_url=success_url
                or f"{settings.frontend_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=cancel_url
                or f"{settings.frontend_url}/dashboard/{license_number}?payment_cancelled=true",
                metadata={
                    "license_number": license_number,
                    "product_type": "cpe_management",
                    "created_by": "supercpe_backend",
                    **(metadata or {}),
                },
                subscription_data={
                    "metadata": {
                        "license_number": license_number,
                        "product_type": "cpe_management",
                    }
                },
                # Allow promotion codes for discounts
                allow_promotion_codes=True,
                # Automatically collect tax if applicable
                automatic_tax={"enabled": True},
            )

            return checkout_session

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating checkout session: {e}")
            raise Exception(f"Payment system error: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating checkout session: {e}")
            raise Exception(f"Failed to create payment session: {str(e)}")

    def _get_or_create_customer(self, email: str, license_number: str):
        """Get existing Stripe customer or create new one"""
        try:
            # Search for existing customer by email
            customers = stripe.Customer.list(email=email, limit=1)

            if customers.data:
                customer = customers.data[0]

                # Update metadata if needed
                if customer.metadata.get("license_number") != license_number:
                    customer = stripe.Customer.modify(
                        customer.id,
                        metadata={
                            **customer.metadata,
                            "license_number": license_number,
                        },
                    )
            else:
                # Create new customer
                customer = stripe.Customer.create(
                    email=email,
                    metadata={
                        "license_number": license_number,
                        "source": "supercpe_backend",
                        "created_at": datetime.now().isoformat(),
                    },
                )

            return customer

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error with customer: {e}")
            raise Exception(f"Customer creation error: {str(e)}")

    def handle_successful_payment(self, checkout_session_id: str):
        """Handle successful payment from Stripe webhook"""
        try:
            # Retrieve the checkout session
            session = stripe.checkout.Session.retrieve(checkout_session_id)

            # Get the subscription
            subscription_id = session.subscription
            if not subscription_id:
                raise Exception("No subscription found in checkout session")

            stripe_subscription = stripe.Subscription.retrieve(subscription_id)

            # Extract metadata
            license_number = session.metadata.get("license_number")
            if not license_number:
                raise Exception("No license number in session metadata")

            # Get or create user
            user = (
                self.db.query(User)
                .filter(User.license_number == license_number)
                .first()
            )
            if not user:
                # Create user if doesn't exist
                cpa = (
                    self.db.query(CPA)
                    .filter(CPA.license_number == license_number)
                    .first()
                )
                if not cpa:
                    raise Exception(f"CPA not found for license {license_number}")

                user = User(
                    email=session.customer_details.email,
                    name=cpa.full_name,
                    license_number=license_number,
                    auth_provider="stripe",
                    is_verified=True,
                    created_at=datetime.now(),
                )
                self.db.add(user)
                self.db.flush()

            # Create or update subscription record - FIXED field name
            existing_subscription = (
                self.db.query(Subscription)
                .filter(
                    Subscription.license_number
                    == license_number  # FIXED: correct field name
                )
                .first()
            )

            if existing_subscription:
                # Update existing subscription
                existing_subscription.stripe_subscription_id = subscription_id
                existing_subscription.status = stripe_subscription.status
                existing_subscription.current_period_start = datetime.fromtimestamp(
                    stripe_subscription.current_period_start
                )
                existing_subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription.current_period_end
                )
                existing_subscription.updated_at = datetime.now()
            else:
                # Create new subscription
                new_subscription = Subscription(
                    user_id=user.id,
                    license_number=license_number,  # FIXED: correct field name
                    stripe_subscription_id=subscription_id,
                    stripe_customer_id=session.customer,
                    status=stripe_subscription.status,
                    current_period_start=datetime.fromtimestamp(
                        stripe_subscription.current_period_start
                    ),
                    current_period_end=datetime.fromtimestamp(
                        stripe_subscription.current_period_end
                    ),
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                self.db.add(new_subscription)

            # Create payment record
            payment = Payment(
                user_id=user.id,
                cpa_license_number=license_number,  # This field exists in Payment model
                stripe_payment_intent_id=session.payment_intent,
                stripe_subscription_id=subscription_id,
                amount=session.amount_total / 100,  # Convert from cents
                currency=session.currency,
                status="completed",
                payment_type="subscription",
                product_type="cpe_management",
                created_at=datetime.now(),
            )
            self.db.add(payment)

            # Mark CPA as premium
            cpa = (
                self.db.query(CPA).filter(CPA.license_number == license_number).first()
            )
            if cpa:
                cpa.is_premium = True

            self.db.commit()

            logger.info(
                f"Successfully processed subscription for license {license_number}"
            )
            return True

        except Exception as e:
            logger.error(f"Error handling successful payment: {e}")
            self.db.rollback()
            raise e

    def _get_plan_name_from_subscription(self, stripe_subscription):
        """Extract plan name from Stripe subscription"""
        try:
            if stripe_subscription.items.data:
                price = stripe_subscription.items.data[0].price
                if price.recurring.interval == "year":
                    return "Professional Annual"
                elif price.recurring.interval == "month":
                    return "Professional Monthly"
            return "Professional Plan"
        except:
            return "Professional Plan"

    def get_pricing_plans(self):
        """Get available pricing plans"""
        return {
            "monthly": {
                "name": "Professional Monthly",
                "price": "$10",
                "period": "month",
                "description": "Perfect for ongoing CPE management",
                "features": [
                    "Unlimited certificate uploads",
                    "Advanced compliance reports",
                    "Priority AI processing",
                    "Secure document vault",
                    "Professional audit presentations",
                    "Multi-year tracking",
                    "Email support",
                ],
            },
            "annual": {
                "name": "Professional Annual",
                "price": "$96",
                "period": "year",
                "monthly_equivalent": "$8/month",
                "savings": "Save $24/year (20% off)",
                "description": "Best value - 2 months free!",
                "popular": True,
                "features": [
                    "Everything in Monthly plan",
                    "2 months FREE (20% savings)",
                    "Priority customer support",
                    "Advanced compliance analytics",
                    "Custom report templates",
                    "Early access to new features",
                ],
            },
        }
