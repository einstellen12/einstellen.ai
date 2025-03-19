from django.db import models
import uuid

class Interview(models.Model):
    candidate_id = models.UUIDField()
    interviewer_id = models.UUIDField()
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    youtube_link = models.TextField(null=True, blank=True)
    local_path = models.TextField(null=True, blank=True)
    link = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)  # Unique link field

    class Meta:
        db_table = 'interviews'

    def __str__(self):
        return f"Interview {self.id} - Link: {self.link}"

class Transcript(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE)
    speaker_type = models.CharField(max_length=20)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transcripts'

class Question(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE)
    content = models.TextField()
    asked = models.BooleanField(default=False)
    diverted = models.BooleanField(default=False)

    class Meta:
        db_table = 'questions'

class Report(models.Model):
    interview = models.ForeignKey(Interview, on_delete=models.CASCADE)
    candidate_id = models.UUIDField()
    transcript_summary = models.TextField(null=True, blank=True)
    ai_evaluation = models.TextField(null=True, blank=True)
    interviewer_feedback = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'reports'