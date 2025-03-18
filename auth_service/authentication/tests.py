from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from .models import User, Tenant, Subscription, Role, UserRole
from .serializers import (
    CandidateSignupSerializer, CandidateLoginSerializer, 
    EmployerSignupSerializer, EmployerLoginSerializer, UserSerializer, UserRoleSerializer
)
from .views import AnomalyDetector
from django_otp.plugins.otp_totp.models import TOTPDevice
import uuid
from unittest.mock import patch
from rest_framework_simplejwt.tokens import RefreshToken
import json
from rest_framework.response import Response

def custom_exception_handler(exc, context):
    from rest_framework.views import exception_handler
    response = exception_handler(exc, context)
    if response is None:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return response

@override_settings(
    REST_FRAMEWORK={
        'EXCEPTION_HANDLER': 'authentication.tests.custom_exception_handler',
        'DEFAULT_PERMISSION_CLASSES': [],
    }
)
class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_tacopilot = Tenant.objects.create(
            name="TACopilotTenant", subdomain=None, tier="TA-Copilot"
        )
        self.tenant_humanadv = Tenant.objects.create(
            name="HumanAdvTenant", subdomain="adv", tier="humanadv"
        )
        Subscription.objects.create(tenant=self.tenant_humanadv, is_active=True)
        self.user = User.objects.create_user(
            phone_number="+1234567890", full_name="Test User", password="testpass123"
        )
        self.role = Role.objects.create(name="TestRole", tenant=self.tenant_tacopilot)
        cache.clear()

    def test_user_model(self):
        self.assertEqual(str(self.user), "+1234567890")
        self.assertTrue(isinstance(self.user.id, uuid.UUID))

    def test_tenant_model(self):
        self.assertEqual(str(self.tenant_tacopilot), "TACopilotTenant (TA-Copilot)")
        self.assertEqual(self.tenant_tacopilot.tier, "TA-Copilot")
        self.assertIsNone(self.tenant_tacopilot.subdomain)

    def test_candidate_signup_unsubscribed_tacopilot(self):
        with patch('django.conf.settings.DJANGO_ENV', 'production'):
            url = reverse("candidate_signup")
            data = {"phone_number": "+5556667777", "full_name": "Candidate"}
            response = self.client.post(
                url, data, HTTP_HOST="api.einstellen.ai", format='json'
            )
            content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("OTP sent to phone", content["message"] if isinstance(content, dict) else content)

    def test_candidate_signup_subscribed_humanadv(self):
        with patch('django.conf.settings.DJANGO_ENV', 'production'):
            url = reverse("candidate_signup")
            data = {"phone_number": "+9998887776", "full_name": "AdvUser"}
            response = self.client.post(
                url, data, HTTP_HOST="api.einstellen.ai", HTTP_X_TENANT_TIER="humanadv", HTTP_X_SUBDOMAIN="adv", format='json'
            )
            content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("OTP sent to phone", content["message"] if isinstance(content, dict) else content)

    def test_candidate_login_unsubscribed_tacopilot(self):
        with patch('django.conf.settings.DJANGO_ENV', 'production'):
            url = reverse("candidate_login")
            data = {"phone_number": "+1234567890"}
            response = self.client.post(
                url, data, HTTP_HOST="api.einstellen.ai", format='json'
            )
            content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn("OTP sent to phone", content["detail"] if isinstance(content, dict) else content)

    def test_user_profile_view(self):
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant_tacopilot.id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        url = reverse("user_profile")
        response = self.client.get(url, HTTP_HOST="api.einstellen.ai")
        content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(json.loads(content)["phone_number"] if isinstance(content, str) else content["phone_number"], "+1234567890")

    def test_assign_role_view(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant_humanadv.id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        url = reverse("assign_role")
        data = {"user": str(self.user.id), "role": str(self.role.id)}
        UserRole.objects.filter(user=self.user, role=self.role, tenant=self.tenant_humanadv).delete()
        response = self.client.post(url, data, HTTP_HOST="api.einstellen.ai", HTTP_X_TENANT_TIER="humanadv", HTTP_X_SUBDOMAIN="adv", format='json')
        content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UserRole.objects.filter(user=self.user, role=self.role, tenant=self.tenant_humanadv).exists())

    def test_setup_mfa_view(self):
        refresh = RefreshToken.for_user(self.user)
        refresh["tenant_id"] = str(self.tenant_tacopilot.id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        url = reverse("mfa_setup")
        TOTPDevice.objects.filter(user=self.user).delete()
        response = self.client.post(url, HTTP_HOST="api.einstellen.ai")
        content = response.content.decode('utf-8') if response.status_code >= 400 else response.data
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("qr_code_url", content if isinstance(content, str) else content)
        self.assertTrue(TOTPDevice.objects.filter(user=self.user).exists())

    def test_anomaly_detector(self):
        detector = AnomalyDetector()
        self.assertFalse(detector.is_trained)
        detector.train()
        self.assertFalse(detector.is_trained)
        self.assertFalse(detector.predict("192.168.1.1", "2025-03-11 10:00:00"))

    def test_generate_otp(self):
        from .serializers import generate_otp
        otp = generate_otp()
        self.assertEqual(len(otp), 6)
        self.assertTrue(otp.isdigit())

    def tearDown(self):
        cache.clear()