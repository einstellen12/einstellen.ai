from rest_framework import serializers
from .models import Notification, Message, InterviewReminder

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'user_id', 'tenant_id', 'notification_type', 'subject', 'message', 'recipient', 'sent_at', 'is_sent', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'sender_id', 'receiver_id', 'tenant_id', 'content', 'sent_at', 'is_read']

class InterviewReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewReminder
        fields = ['id', 'application_id', 'tenant_id', 'candidate_id', 'employer_id', 'interview_time', 'reminder_time', 'is_sent', 'created_at']