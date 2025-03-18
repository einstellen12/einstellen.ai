from rest_framework import serializers
from .models import Candidate, Education, WorkExperience, Skill, Certification, Interview, InterviewInsight

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['id', 'degree', 'university', 'start_year', 'end_year']

class WorkExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkExperience
        fields = ['id', 'company_name', 'job_title', 'start_date', 'end_date']

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'skill_name']

class CertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certification
        fields = ['id', 'title', 'issued_by', 'issue_date']

class InterviewInsightSerializer(serializers.ModelSerializer):
    skills_detected = serializers.ListField(child=serializers.CharField())

    class Meta:
        model = InterviewInsight
        fields = ['id', 'overall_score', 'communication_score', 'technical_score', 'problem_solving_score', 'skills_detected']

class InterviewSerializer(serializers.ModelSerializer):
    insights = InterviewInsightSerializer(read_only=True)

    class Meta:
        model = Interview
        fields = ['id', 'application_id', 'scheduled_at', 'status', 'video_url', 'insights', 'created_at', 'updated_at']

class CandidateSerializer(serializers.ModelSerializer):
    education = EducationSerializer(many=True, read_only=True)
    work_experience = WorkExperienceSerializer(many=True, read_only=True)
    skills = SkillSerializer(many=True, read_only=True)
    certifications = CertificationSerializer(many=True, read_only=True)
    interviews = InterviewSerializer(many=True, read_only=True)

    class Meta:
        model = Candidate
        fields = [
            'id', 'user_id', 'tenant_id', 'first_name', 'last_name', 'dob', 'gender', 'phone', 'location',
            'education', 'work_experience', 'skills', 'certifications', 'interviews', 'created_at', 'updated_at'
        ]
        extra_kwargs = {'tenant_id': {'required': False, 'allow_null': True}}