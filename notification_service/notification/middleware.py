from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, JsonResponse
import jwt
from django.conf import settings
from .logger import logger

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        if request.path.startswith('/admin/'):
            return None

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            logger.warning("No Authorization token provided")
            return JsonResponse({"error": "Authentication required", "details": "No token provided"}, status=401)

        try:
            payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
            request.user_id = payload['user_id']
            request.tenant_id = payload['tenant_id']
        except jwt.ExpiredSignatureError:
            logger.warning(f"Expired JWT token: {token}")
            return JsonResponse({"error": "Token expired", "details": "Please refresh your token"}, status=401)
        except jwt.InvalidTokenError:
            logger.warning(f"Invalid JWT token: {token}")
            return JsonResponse({"error": "Invalid token", "details": "Token is not valid"}, status=401)
        except Exception as e:
            logger.error(f"JWT authentication failed: {e}")
            return JsonResponse({"error": "Authentication failed", "details": str(e)}, status=500)