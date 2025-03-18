from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AuditLog


# @receiver(post_save, sender=AuditLog)
# def log_audit_creation(sender, instance, created, **kwargs):
#     if created:
#         print(f"Audit log created: {instance.id}")