from django.utils.deprecation import MiddlewareMixin
from audit.models import AuditLog
from django.http import HttpRequest

class AuditMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        request.audit_data = {"ip_address": request.META.get("REMOTE_ADDR")}

    def process_response(self, request, response):
        if hasattr(request, "audit_action"):
            AuditLog.objects.create(
                user=getattr(request, "user", None),
                action=request.audit_action,
                ip_address=request.audit_data["ip_address"],
                tenant=request.META.get("HTTP_HOST").split(".")[0],
                details=getattr(request, "audit_details", None),
            )
        return response