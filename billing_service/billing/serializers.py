from rest_framework import serializers
from .models import Plan, Subscription, Invoice, CreditUsage, Referral

class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ['id', 'name', 'description', 'price', 'billing_cycle', 'credits', 'created_at']

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    available_credits = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ['id', 'tenant_id', 'plan', 'payment_method', 'payment_id', 'status', 'start_date', 'end_date', 
                  'auto_renew', 'daily_credits', 'referral_credits', 'available_credits', 'created_at', 'updated_at']

    def get_available_credits(self, obj):
        return obj.get_available_credits()

class InvoiceSerializer(serializers.ModelSerializer):
    subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'subscription', 'amount', 'status', 'invoice_date', 'due_date', 'payment_id', 'created_at']

class CreditUsageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CreditUsage
        fields = ['id', 'subscription', 'amount', 'reason', 'used_at']

class ReferralSerializer(serializers.ModelSerializer):
    referrer_subscription = SubscriptionSerializer(read_only=True)
    referred_subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = Referral
        fields = ['id', 'referrer_subscription', 'referred_subscription', 'interviews_completed', 'reward_granted', 'created_at']