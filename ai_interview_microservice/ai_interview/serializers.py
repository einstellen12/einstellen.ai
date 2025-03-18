from rest_framework import serializers
from .models import Interview, Transcript, QuestionAnswer, FeedbackReport

class TranscriptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transcript
        fields = ['id', 'interview', 'text', 'timestamp']

class QuestionAnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionAnswer
        fields = ['id', 'interview', 'question', 'answer', 'code', 'is_deviated', 'score', 'asked_at']

class InterviewSerializer(serializers.ModelSerializer):
    transcripts = TranscriptSerializer(many=True, read_only=True)
    questions_answers = QuestionAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = Interview
        fields = ['id', 'tenant_id', 'subscription_id', 'candidate_id', 'status', 'start_time', 'end_time', 'resume', 'job_description', 'created_at', 'transcripts', 'questions_answers']

class FeedbackReportSerializer(serializers.ModelSerializer):
    interview = InterviewSerializer(read_only=True)

    class Meta:
        model = FeedbackReport
        fields = ['id', 'interview', 'overall_score', 'detailed_scores', 'comments', 'generated_at']