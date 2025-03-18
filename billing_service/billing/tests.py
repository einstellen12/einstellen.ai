from django.test import TestCase
from rest_framework.test import APIClient
from .models import Plan, Subscription, Referral
from django.utils import timezone
import uuid

class BillingTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_id = uuid.uuid4()
        self.plan_tacopilot = Plan.objects.create(name='TA-Copilot', description='Free plan', price=0.00, credits=0)
        self.plan_humanadv = Plan.objects.create(name='humanadv', description='Advanced plan', price=50.00, credits=10)
        self.subscription_tacopilot = Subscription.objects.create(
            tenant_id=self.tenant_id,
            plan=self.plan_tacopilot,
            payment_method=None,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            status='active',
            daily_credits=5
        )
        self.subscription_humanadv = Subscription.objects.create(
            tenant_id=uuid.uuid4(),
            plan=self.plan_humanadv,
            payment_method='stripe',
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            status='active',
            daily_credits=10
        )

    def test_consume_credits_tacopilot_employer(self):
        url = f'/subscriptions/{self.subscription_tacopilot.id}/consume-credits/'
        response = self.client.post(url, {'credits': 2, 'is_candidate': False}, format='json')
        self.assertEqual(response.status_code, 200)
        self.subscription_tacopilot.refresh_from_db()
        self.assertEqual(self.subscription_tacopilot.daily_credits, 3)

    def test_consume_credits_tacopilot_candidate(self):
        url = f'/subscriptions/{self.subscription_tacopilot.id}/consume-credits/'
        response = self.client.post(url, {'credits': 2, 'is_candidate': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.subscription_tacopilot.refresh_from_db()
        self.assertEqual(self.subscription_tacopilot.daily_credits, 5)  # No deduction for candidates

    def test_referral_reward(self):
        referred_subscription = Subscription.objects.create(
            tenant_id=uuid.uuid4(),
            plan=self.plan_tacopilot,
            start_date=timezone.now(),
            end_date=timezone.now() + timezone.timedelta(days=30),
            status='active',
            daily_credits=5
        )
        referral = Referral.objects.create(
            referrer_subscription=self.subscription_tacopilot,
            referred_subscription=referred_subscription
        )
        url = f'/subscriptions/{referred_subscription.id}/consume-credits/'
        for _ in range(5):
            self.client.post(url, {'credits': 1, 'is_candidate': False}, format='json')
        referral.refresh_from_db()
        self.subscription_tacopilot.refresh_from_db()
        self.assertEqual(referral.interviews_completed, 5)
        self.assertTrue(referral.reward_granted)
        self.assertEqual(self.subscription_tacopilot.referral_credits, 1)