from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from twilio.rest import Client
from django.conf import settings
from .models import Notification, Message, InterviewReminder
from .serializers import NotificationSerializer, MessageSerializer, InterviewReminderSerializer
from .logger import logger
from audit.models import AuditLog
from django.utils import timezone
import redis

redis_client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

class SendNotificationView(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            data['user_id'] = request.user_id
            data['tenant_id'] = request.tenant_id
            serializer = NotificationSerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Notification validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            notification = serializer.save()

            if notification.notification_type == 'email':
                send_mail(
                    subject=notification.subject,
                    message=notification.message,
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[notification.recipient],
                    fail_silently=False,
                )
            elif notification.notification_type == 'sms':
                client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                client.messages.create(
                    body=notification.message,
                    from_=settings.TWILIO_PHONE,
                    to=notification.recipient
                )

            notification.is_sent = True
            notification.sent_at = timezone.now()
            notification.save()

            request.audit_action = "Send Notification"
            request.audit_details = {"notification_id": str(notification.id)}
            logger.info(f"Notification sent: {notification.id}")
            return Response({"notification_id": str(notification.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Notification sending failed: {e}")
            return Response({"error": "Sending failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListNotificationsView(APIView):
    def get(self, request):
        try:
            notifications = Notification.objects.filter(user_id=request.user_id, tenant_id=request.tenant_id)
            serializer = NotificationSerializer(notifications, many=True)
            request.audit_action = "List Notifications"
            request.audit_details = {"user_id": str(request.user_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Notification listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SendMessageView(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            data['sender_id'] = request.user_id
            data['tenant_id'] = request.tenant_id
            serializer = MessageSerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Message validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            message = serializer.save()
            redis_client.publish(f'chat_{data["receiver_id"]}', json.dumps({
                'message': message.content,
                'sender_id': str(message.sender_id),
                'sent_at': message.sent_at.isoformat()
            }))

            request.audit_action = "Send Message"
            request.audit_details = {"message_id": str(message.id)}
            logger.info(f"Message sent: {message.id}")
            return Response({"message_id": str(message.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Message sending failed: {e}")
            return Response({"error": "Sending failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListMessagesView(APIView):
    def get(self, request):
        try:
            messages = Message.objects.filter(
                tenant_id=request.tenant_id
            ).filter(models.Q(sender_id=request.user_id) | models.Q(receiver_id=request.user_id))
            serializer = MessageSerializer(messages, many=True)
            request.audit_action = "List Messages"
            request.audit_details = {"user_id": str(request.user_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Message listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CreateInterviewReminderView(APIView):
    def post(self, request):
        try:
            data = request.data.copy()
            data['tenant_id'] = request.tenant_id
            serializer = InterviewReminderSerializer(data=data)
            if not serializer.is_valid():
                logger.warning(f"Reminder validation failed: {serializer.errors}")
                return Response({"error": "Validation failed", "details": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            reminder = serializer.save()
            redis_client.setex(
                f"reminder_{reminder.id}",
                int((reminder.reminder_time - timezone.now()).total_seconds()),
                reminder.id
            )

            request.audit_action = "Create Interview Reminder"
            request.audit_details = {"reminder_id": str(reminder.id)}
            logger.info(f"Interview reminder created: {reminder.id}")
            return Response({"reminder_id": str(reminder.id)}, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Reminder creation failed: {e}")
            return Response({"error": "Creation failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ListInterviewRemindersView(APIView):
    def get(self, request):
        try:
            reminders = InterviewReminder.objects.filter(
                tenant_id=request.tenant_id,
                candidate_id=request.user_id
            ) | InterviewReminder.objects.filter(
                tenant_id=request.tenant_id,
                employer_id=request.user_id
            )
            serializer = InterviewReminderSerializer(reminders, many=True)
            request.audit_action = "List Interview Reminders"
            request.audit_details = {"user_id": str(request.user_id)}
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Reminder listing failed: {e}")
            return Response({"error": "Listing failed", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)