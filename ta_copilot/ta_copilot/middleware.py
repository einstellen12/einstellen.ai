from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, JsonResponse
from django.conf import settings
import requests

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request: HttpRequest):
        if request.path.startswith('/admin/'):
            return None

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return JsonResponse({"error": "Authentication required", "details": "No token provided"}, status=401)

        try:
            auth_service_url = f"{settings.AUTH_SERVICE_URL}/verify-token/"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.post(auth_service_url, headers=headers, timeout=5)

            if response.status_code == 200:
                payload = response.json()
                # Extract auth_info from the response
                auth_info = payload.get('auth_info')
                if not auth_info:
                    return JsonResponse({"error": "Invalid token", "details": "Missing auth_info"}, status=401)
                
                user_info = auth_info.get('user', {})
                tenant_info = auth_info.get('tenant', {})
                
                request.user_id = user_info.get('id')
                request.tenant_id = tenant_info.get('id')
                
                if not request.user_id:
                    return JsonResponse({"error": "Invalid token", "details": "Missing user_id"}, status=401)
                
                request.user_info = user_info
                request.tenant_info = tenant_info
                
            elif response.status_code == 401:
                error = response.json().get('error', 'Unknown error')
                return JsonResponse({"error": error, "details": "Token validation failed"}, status=401)
            else:
                return JsonResponse({"error": "Authentication failed", "details": "Unexpected response from auth service"}, status=500)

        except requests.exceptions.RequestException as e:
            return JsonResponse({"error": "Authentication service unavailable", "details": str(e)}, status=503)
        except ValueError as e:
            return JsonResponse({"error": "Authentication failed", "details": "Invalid response format"}, status=500)
        except Exception as e:
            return JsonResponse({"error": "Authentication failed", "details": str(e)}, status=500)