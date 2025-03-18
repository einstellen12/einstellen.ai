import stripe
import razorpay
import paypalrestsdk
from django.conf import settings
from .logger import logger
from datetime import timedelta
from django.utils import timezone
import os

stripe.api_key = settings.STRIPE_SECRET_KEY
paypalrestsdk.configure({
    "mode": settings.PAYPAL_MODE,
    "client_id": settings.PAYPAL_CLIENT_ID,
    "client_secret": settings.PAYPAL_CLIENT_SECRET
})
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def process_stripe_payment(plan, subscription):
    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=int(plan.price * 100),
            currency="usd",
            description=f"Subscription to {plan.name}",
            metadata={"subscription_id": str(subscription.id)}
        )
        return payment_intent.id
    except Exception as e:
        logger.error(f"Stripe payment failed: {e}")
        raise

def process_razorpay_payment(plan, subscription):
    try:
        order = razorpay_client.order.create({
            "amount": int(plan.price * 100),
            "currency": "INR",
            "payment_capture": 1,
            "notes": {"subscription_id": str(subscription.id)}
        })
        return order["id"]
    except Exception as e:
        logger.error(f"Razorpay payment failed: {e}")
        raise

def process_paypal_payment(plan, subscription):
    try:
        payment = paypalrestsdk.Payment({
            "intent": "sale",
            "payer": {"payment_method": "paypal"},
            "transactions": [{
                "amount": {"total": str(plan.price), "currency": "USD"},
                "description": f"Subscription to {plan.name}"
            }],
            "redirect_urls": {
                "return_url": os.getenv("PAYPAL_RETURN_URL"),
                "cancel_url": os.getenv("PAYPAL_CANCEL_URL")
            }
        })
        if payment.create():
            return payment.id
        else:
            logger.error(f"PayPal payment creation failed: {payment.error}")
            raise Exception(payment.error)
    except Exception as e:
        logger.error(f"PayPal payment failed: {e}")
        raise

def create_invoice(subscription):
    from .models import Invoice
    try:
        due_date = timezone.now() + timedelta(days=7)
        invoice = Invoice.objects.create(
            subscription=subscription,
            amount=subscription.plan.price,
            due_date=due_date
        )
        return invoice
    except Exception as e:
        logger.error(f"Invoice creation failed: {e}")
        raise