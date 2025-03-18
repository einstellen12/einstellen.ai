from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, JsonResponse
from django.conf import settings
import requests
from .logger import logger

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        if request.path.startswith('/admin/') or request.path == '/webhook/stripe/':
            return None

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            logger.warning("No Authorization token provided")
            return JsonResponse({"error": "Authentication required", "details": "No token provided"}, status=401)

        try:
            auth_service_url = f"{settings.AUTH_SERVICE_URL}/verify-token/"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.post(auth_service_url, headers=headers, timeout=20)

            if response.status_code == 200:
                payload = response.json()
                request.user_id = payload.get('user_id')
                request.tenant_id = payload.get('tenant_id')
                if not request.user_id or not request.tenant_id:
                    logger.warning(f"Invalid payload from auth service: {payload}")
                    return JsonResponse({"error": "Invalid token", "details": "Missing user_id or tenant_id"}, status=401)
            elif response.status_code == 401:
                error = response.json().get('error', 'Unknown error')
                logger.warning(f"Auth service rejected token: {error}")
                return JsonResponse({"error": error, "details": "Token validation failed"}, status=401)
            else:
                logger.error(f"Unexpected response from auth service: {response.status_code} - {response.text}")
                return JsonResponse({"error": "Authentication failed", "details": "Unexpected response from auth service"}, status=500)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to auth service: {e}")
            return JsonResponse({"error": "Authentication service unavailable", "details": str(e)}, status=503)
        except ValueError as e:
            logger.error(f"Invalid response from auth service: {e}")
            return JsonResponse({"error": "Authentication failed", "details": "Invalid response format"}, status=500)
        except Exception as e:
            logger.error(f"JWT authentication failed: {e}")
            return JsonResponse({"error": "Authentication failed", "details": str(e)}, status=500)