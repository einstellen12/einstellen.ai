from django.db import models
from django.conf import settings
from authentication.models import User, Tenant
import uuid

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    ip_address = models.CharField(max_length=45)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"