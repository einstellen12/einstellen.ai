from rest_framework import serializers
from .models import Company, Job, Application

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['id', 'name', 'tenant_id', 'created_at']

class JobSerializer(serializers.ModelSerializer):
    company = CompanySerializer(read_only=True)

    class Meta:
        model = Job
        fields = ['id', 'company', 'title', 'description', 'location', 'salary_range', 'key_skills', 'created_at', 'updated_at']

class ApplicationSerializer(serializers.ModelSerializer):
    job = JobSerializer(read_only=True)

    class Meta:
        model = Application
        fields = ['id', 'job', 'candidate_id', 'status', 'applied_at', 'updated_at', 'match_score']