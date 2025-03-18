from django.test import TestCase
from rest_framework.test import APIClient
from .models import Candidate, Education
from django.utils import timezone
import uuid

class CandidateTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_id = uuid.uuid4()
        self.tenant_id = uuid.uuid4()
        self.candidate_with_tenant = Candidate.objects.create(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            first_name="John",
            last_name="Doe",
            phone="+1234567890"
        )
        self.candidate_without_tenant = Candidate.objects.create(
            user_id=uuid.uuid4(),
            tenant_id=None,
            first_name="Jane",
            last_name="Smith",
            phone="+0987654321"
        )

    def test_create_candidate_profile_with_tenant(self):
        data = {
            "first_name": "Alice",
            "last_name": "Johnson",
            "phone": "+1122334455"
        }
        self.client.force_authenticate(user=None, token="dummy-token-with-tenant")
        response = self.client.post('/candidates/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn("candidate_id", response.data)

    def test_create_candidate_profile_without_tenant(self):
        data = {
            "first_name": "Bob",
            "last_name": "Wilson",
            "phone": "+5566778899"
        }
        self.client.force_authenticate(user=None, token="dummy-token-no-tenant")
        response = self.client.post('/candidates/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn("candidate_id", response.data)

    def test_get_candidate_profile_with_tenant(self):
        self.client.force_authenticate(user=None, token="dummy-token-with-tenant")
        response = self.client.get(f'/candidates/{self.candidate_with_tenant.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "John")

    def test_get_candidate_profile_without_tenant(self):
        self.client.force_authenticate(user=None, token="dummy-token-no-tenant")
        response = self.client.get(f'/candidates/{self.candidate_without_tenant.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["first_name"], "Jane")

    def test_add_education_without_tenant(self):
        data = {
            "degree": "B.Sc",
            "university": "Test University",
            "start_year": 2018,
            "end_year": 2022
        }
        self.client.force_authenticate(user=None, token="dummy-token-no-tenant")
        response = self.client.post(f'/candidates/{self.candidate_without_tenant.id}/education/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn("education_id", response.data)