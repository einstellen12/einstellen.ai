from django.db import models
import uuid
from django.utils import timezone

class Interview(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField()
    subscription_id = models.UUIDField()
    candidate_id = models.UUIDField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    resume = models.TextField(null=True, blank=True)
    job_description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview {self.id} for {self.candidate_id}"

class Transcript(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='transcripts')
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Transcript for {self.interview} at {self.timestamp}"

class QuestionAnswer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name='questions_answers')
    question = models.TextField()
    answer = models.TextField(null=True, blank=True)
    code = models.TextField(null=True, blank=True)
    is_deviated = models.BooleanField(default=False, help_text="True if interviewer deviated from AI question")
    score = models.FloatField(null=True, blank=True)
    asked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Q&A for {self.interview} - {self.question[:50]}"

class FeedbackReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='feedback')
    overall_score = models.FloatField()
    detailed_scores = models.JSONField(default=dict, help_text="Scores per question")
    comments = models.TextField()
    generated_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback for {self.interview}"