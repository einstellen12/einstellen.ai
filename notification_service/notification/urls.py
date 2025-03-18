from django.urls import path
from .views import (
    SendNotificationView, ListNotificationsView,
    SendMessageView, ListMessagesView,
    CreateInterviewReminderView, ListInterviewRemindersView
)

urlpatterns = [
    path('notifications/send/', SendNotificationView.as_view(), name='send_notification'),
    path('notifications/', ListNotificationsView.as_view(), name='list_notifications'),
    path('messages/send/', SendMessageView.as_view(), name='send_message'),
    path('messages/', ListMessagesView.as_view(), name='list_messages'),
    path('reminders/create/', CreateInterviewReminderView.as_view(), name='create_reminder'),
    path('reminders/', ListInterviewRemindersView.as_view(), name='list_reminders'),
]