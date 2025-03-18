from django.db import models
import uuid
from django.utils import timezone
from django.db.models import F

class Plan(models.Model):
    PLAN_CHOICES = (
        ('TA-Copilot', 'TA-Copilot'),
        ('humanadv', 'HumanAdv'),
        ('humanpro', 'HumanPro'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, choices=PLAN_CHOICES, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=20, default='monthly')
    credits = models.PositiveIntegerField(default=0, help_text="Base credits provided by this plan")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Subscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField()
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='subscriptions')
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    auto_renew = models.BooleanField(default=True)
    daily_credits = models.PositiveIntegerField(default=0, help_text="Daily credits reset each day")
    referral_credits = models.PositiveIntegerField(default=0, help_text="Credits from referrals, carry forward")
    last_reset = models.DateTimeField(default=timezone.now, help_text="Last daily credit reset time")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.plan.name} for {self.tenant_id}"

    def reset_daily_credits(self):
        if (timezone.now() - self.last_reset).days >= 1:
            if self.plan.name == 'TA-Copilot':
                self.daily_credits = 5
            else:
                self.daily_credits = self.plan.credits
            self.last_reset = timezone.now()
            self.save()

    def get_available_credits(self):
        self.reset_daily_credits()
        return self.daily_credits + self.referral_credits

    def use_credits(self, amount, is_candidate=False):
        self.reset_daily_credits()
        if is_candidate and self.plan.name == 'TA-Copilot':
            return True 
        available_credits = self.get_available_credits()
        if available_credits < amount:
            return False
        if self.daily_credits >= amount:
            self.daily_credits -= amount
        else:
            remaining = amount - self.daily_credits
            self.daily_credits = 0
            self.referral_credits -= remaining
        self.save()
        return True

class Invoice(models.Model):
    STATUS_CHOICES = (
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
        ('failed', 'Failed'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unpaid')
    invoice_date = models.DateTimeField(auto_now_add=True)
    due_date = models.DateTimeField()
    payment_id = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Invoice {self.id} for {self.subscription}"

class CreditUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='credit_usages')
    amount = models.PositiveIntegerField(help_text="Number of credits used")
    reason = models.CharField(max_length=255, default="Interview scheduled")
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} credits used for {self.subscription} at {self.used_at}"

class Referral(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referrer_subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='referrals_made')
    referred_subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='referrals_received')
    interviews_completed = models.PositiveIntegerField(default=0)
    reward_granted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Referral from {self.referrer_subscription} to {self.referred_subscription}"

    def check_reward(self):
        if self.interviews_completed >= 5 and not self.reward_granted:
            self.referrer_subscription.referral_credits = F('referral_credits') + 1
            self.referrer_subscription.save()
            self.reward_granted = True
            self.save()