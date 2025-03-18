from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
import stripe
from .models import Plan, Subscription, Invoice, CreditUsage, Referral
from .serializers import PlanSerializer, SubscriptionSerializer, InvoiceSerializer, CreditUsageSerializer, ReferralSerializer
from .logger import logger
from audit.models import AuditLog
from django.conf import settings
from .payment_handlers import (
    process_stripe_payment, process_razorpay_payment, process_paypal_payment, create_invoice
)

class ListPlansView(APIView):
    def get(self, request):
        try:
            plans = Plan.objects.all()
            serializer = PlanSerializer(plans, many=True)
            AuditLog.objects.create(
                user_id=request.user_id, action="List Plans", tenant_id=request.tenant_id,
                details={"tenant_id": str(request.tenant_id)}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Plan listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateSubscriptionView(APIView):
    def post(self, request):
        try:
            plan = Plan.objects.get(id=request.data.get('plan_id'))
            data = request.data.copy()
            data['tenant_id'] = request.tenant_id
            data['plan'] = plan.id
            data['start_date'] = timezone.now()
            data['end_date'] = timezone.now() + timedelta(days=30 if plan.name == 'TA-Copilot' else 30)
            serializer = SubscriptionSerializer(data=data)
            serializer.is_valid(raise_exception=True)

            subscription = serializer.save()
            if plan.name == 'TA-Copilot':
                subscription.daily_credits = 5
                subscription.payment_method = None
                subscription.status = 'active'
            else:
                payment_method = data.get('payment_method')
                if payment_method == 'stripe':
                    payment_id = process_stripe_payment(plan, subscription)
                elif payment_method == 'razorpay':
                    payment_id = process_razorpay_payment(plan, subscription)
                elif payment_method == 'paypal':
                    payment_id = process_paypal_payment(plan, subscription)
                else:
                    return Response({"error": "Invalid payment method"}, status=status.HTTP_400_BAD_REQUEST)
                subscription.payment_id = payment_id

            subscription.save()
            if plan.name != 'TA-Copilot':
                invoice = create_invoice(subscription)

            AuditLog.objects.create(
                user_id=request.user_id, action="Create Subscription", tenant_id=request.tenant_id,
                details={"subscription_id": str(subscription.id), "plan": plan.name}
            )
            logger.info(f"Subscription created: {subscription.id}")
            return Response({"subscription_id": str(subscription.id), "payment_id": subscription.payment_id}, status=status.HTTP_201_CREATED)
        except Plan.DoesNotExist:
            logger.warning(f"Plan not found: {request.data.get('plan_id')}")
            return Response({"error": "Not found", "details": "Plan does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Subscription creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetSubscriptionView(APIView):
    def get(self, request, subscription_id):
        try:
            subscription = Subscription.objects.get(id=subscription_id, tenant_id=request.tenant_id)
            serializer = SubscriptionSerializer(subscription)
            AuditLog.objects.create(
                user_id=request.user_id, action="Get Subscription", tenant_id=request.tenant_id,
                details={"subscription_id": str(subscription_id)}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Subscription.DoesNotExist:
            logger.warning(f"Subscription not found: {subscription_id}")
            return Response({"error": "Not found", "details": "Subscription does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Subscription retrieval failed: {e}")
            return Response({"error": "Retrieval failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CancelSubscriptionView(APIView):
    def post(self, request, subscription_id):
        try:
            subscription = Subscription.objects.get(id=subscription_id, tenant_id=request.tenant_id)
            if subscription.status != 'active':
                return Response({"error": "Invalid status", "details": "Subscription is not active"}, status=status.HTTP_400_BAD_REQUEST)
            
            subscription.status = 'cancelled'
            subscription.auto_renew = False
            subscription.save()
            
            AuditLog.objects.create(
                user_id=request.user_id, action="Cancel Subscription", tenant_id=request.tenant_id,
                details={"subscription_id": str(subscription_id)}
            )
            logger.info(f"Subscription cancelled: {subscription_id}")
            return Response({"message": "Subscription cancelled successfully"}, status=status.HTTP_200_OK)
        except Subscription.DoesNotExist:
            logger.warning(f"Subscription not found: {subscription_id}")
            return Response({"error": "Not found", "details": "Subscription does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Subscription cancellation failed: {e}")
            return Response({"error": "Cancellation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListInvoicesView(APIView):
    def get(self, request):
        try:
            invoices = Invoice.objects.filter(subscription__tenant_id=request.tenant_id)
            serializer = InvoiceSerializer(invoices, many=True)
            AuditLog.objects.create(
                user_id=request.user_id, action="List Invoices", tenant_id=request.tenant_id,
                details={"tenant_id": str(request.tenant_id)}
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Invoice listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PayInvoiceView(APIView):
    def post(self, request, invoice_id):
        try:
            invoice = Invoice.objects.get(id=invoice_id, subscription__tenant_id=request.tenant_id)
            if invoice.status == 'paid':
                return Response({"error": "Already paid", "details": "Invoice is already paid"}, status=status.HTTP_400_BAD_REQUEST)

            subscription = invoice.subscription
            payment_method = subscription.payment_method

            if payment_method == 'stripe':
                payment_id = process_stripe_payment(subscription.plan, subscription)
            elif payment_method == 'razorpay':
                payment_id = process_razorpay_payment(subscription.plan, subscription)
            elif payment_method == 'paypal':
                payment_id = process_paypal_payment(subscription.plan, subscription)
            else:
                return Response({"error": "Invalid payment method"}, status=status.HTTP_400_BAD_REQUEST)

            invoice.payment_id = payment_id
            invoice.status = 'paid'
            invoice.save()

            subscription.status = 'active'
            subscription.save()

            AuditLog.objects.create(
                user_id=request.user_id, action="Pay Invoice", tenant_id=request.tenant_id,
                details={"invoice_id": str(invoice_id), "payment_id": payment_id}
            )
            logger.info(f"Invoice paid: {invoice_id}")
            return Response({"message": "Invoice paid successfully", "payment_id": payment_id}, status=status.HTTP_200_OK)
        except Invoice.DoesNotExist:
            logger.warning(f"Invoice not found: {invoice_id}")
            return Response({"error": "Not found", "details": "Invoice does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Invoice payment failed: {e}")
            return Response({"error": "Payment failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StripeWebhookView(APIView):
    def post(self, request):
        try:
            payload = request.body
            sig_header = request.headers.get('Stripe-Signature')
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)

            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                subscription_id = payment_intent['metadata'].get('subscription_id')
                subscription = Subscription.objects.get(id=subscription_id)
                invoice = Invoice.objects.filter(subscription=subscription, status='unpaid').first()
                if invoice:
                    invoice.status = 'paid'
                    invoice.payment_id = payment_intent['id']
                    invoice.save()
                    subscription.status = 'active'
                    subscription.save()
                    logger.info(f"Stripe payment succeeded for subscription: {subscription_id}")

            AuditLog.objects.create(
                user_id=None, action="Stripe Webhook", tenant_id=subscription.tenant_id if 'subscription_id' in locals() else None,
                details={"event_type": event['type'], "subscription_id": subscription_id}
            )
            return Response({"message": "Webhook received"}, status=status.HTTP_200_OK)
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {e}")
            return Response({"error": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {e}")
            return Response({"error": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Stripe webhook processing failed: {e}")
            return Response({"error": "Webhook failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ConsumeCreditsView(APIView):
    def post(self, request, subscription_id):
        try:
            subscription = Subscription.objects.get(id=subscription_id, tenant_id=request.tenant_id)
            if subscription.status != 'active':
                return Response({"error": "Invalid status", "details": "Subscription is not active"}, status=status.HTTP_400_BAD_REQUEST)

            credits_to_use = request.data.get('credits', 1)
            is_candidate = request.data.get('is_candidate', False)
            if not isinstance(credits_to_use, int) or credits_to_use <= 0:
                return Response({"error": "Invalid credits", "details": "Credits must be a positive integer"}, status=status.HTTP_400_BAD_REQUEST)

            if subscription.use_credits(credits_to_use, is_candidate):
                credit_usage = CreditUsage.objects.create(
                    subscription=subscription,
                    amount=credits_to_use,
                    reason="Interview scheduled"
                )
                if not is_candidate:
                    referrals = Referral.objects.filter(referred_subscription=subscription)
                    for referral in referrals:
                        referral.interviews_completed += credits_to_use
                        referral.check_reward()
                        referral.save()

                AuditLog.objects.create(
                    user_id=request.user_id, action="Consume Credits", tenant_id=request.tenant_id,
                    details={"subscription_id": str(subscription_id), "credits_used": credits_to_use}
                )
                logger.info(f"Credits consumed: {credits_to_use} for subscription {subscription_id}")
                return Response({"message": "Credits consumed successfully", "available_credits": subscription.get_available_credits()}, status=status.HTTP_200_OK)
            else:
                logger.warning(f"Insufficient credits for subscription: {subscription_id}")
                return Response({"error": "Insufficient credits", "details": "Not enough credits available"}, status=status.HTTP_400_BAD_REQUEST)
        except Subscription.DoesNotExist:
            logger.warning(f"Subscription not found: {subscription_id}")
            return Response({"error": "Not found", "details": "Subscription does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Credit consumption failed: {e}")
            return Response({"error": "Consumption failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateReferralView(APIView):
    def post(self, request):
        try:
            referrer_subscription = Subscription.objects.get(id=request.data.get('referrer_subscription_id'), tenant_id=request.tenant_id)
            referred_tenant_id = request.data.get('referred_tenant_id')
            referred_subscription = Subscription.objects.filter(tenant_id=referred_tenant_id).first()

            if not referred_subscription:
                plan = Plan.objects.get(name='TA-Copilot')
                referred_subscription = Subscription.objects.create(
                    tenant_id=referred_tenant_id,
                    plan=plan,
                    start_date=timezone.now(),
                    end_date=timezone.now() + timedelta(days=30),
                    status='active',
                    daily_credits=5
                )

            referral = Referral.objects.create(
                referrer_subscription=referrer_subscription,
                referred_subscription=referred_subscription
            )

            AuditLog.objects.create(
                user_id=request.user_id, action="Create Referral", tenant_id=request.tenant_id,
                details={"referral_id": str(referral.id), "referrer": str(referrer_subscription.id), "referred": str(referred_subscription.id)}
            )
            logger.info(f"Referral created: {referral.id}")
            return Response({"referral_id": str(referral.id)}, status=status.HTTP_201_CREATED)
        except Subscription.DoesNotExist:
            logger.warning(f"Subscription not found: {request.data.get('referrer_subscription_id')}")
            return Response({"error": "Not found", "details": "Referrer subscription does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Plan.DoesNotExist:
            logger.warning("TA-Copilot plan not found")
            return Response({"error": "Not found", "details": "Default plan does not exist"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Referral creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)