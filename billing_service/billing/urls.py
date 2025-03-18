from django.urls import path
from .views import (
    ListPlansView, CreateSubscriptionView, GetSubscriptionView,
    CancelSubscriptionView, ListInvoicesView, PayInvoiceView,
    StripeWebhookView, ConsumeCreditsView, CreateReferralView
)

urlpatterns = [
    path('plans/', ListPlansView.as_view(), name='list_plans'),
    path('subscriptions/create/', CreateSubscriptionView.as_view(), name='create_subscription'),
    path('subscriptions/<uuid:subscription_id>/', GetSubscriptionView.as_view(), name='get_subscription'),
    path('subscriptions/<uuid:subscription_id>/cancel/', CancelSubscriptionView.as_view(), name='cancel_subscription'),
    path('subscriptions/<uuid:subscription_id>/consume-credits/', ConsumeCreditsView.as_view(), name='consume_credits'),
    path('invoices/', ListInvoicesView.as_view(), name='list_invoices'),
    path('invoices/<uuid:invoice_id>/pay/', PayInvoiceView.as_view(), name='pay_invoice'),
    path('webhook/stripe/', StripeWebhookView.as_view(), name='stripe_webhook'),
    path('referrals/create/', CreateReferralView.as_view(), name='create_referral'),
]