from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status, permissions
from rest_framework.throttling import UserRateThrottle
from datetime import datetime
from django.conf import settings
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_otp import devices_for_user
import qrcode
import base64
from io import BytesIO
from social_core.backends.google import GoogleOAuth2
from requests import HTTPError
from time import sleep
from django.core.cache import cache
import redis
from sklearn.ensemble import IsolationForest
import pandas as pd
from .models import User, Role, UserRole, Tenant
from audit.models import AuditLog
from .serializers import (
    CandidateSignupSerializer, CandidateLoginSerializer, EmployerSignupSerializer,
    EmployerLoginSerializer, UserSerializer, UserRoleSerializer
)
from common.logger import logger
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.tokens import AccessToken
import jwt

try:
    redis_client = redis.StrictRedis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=0,
        decode_responses=True,
        socket_timeout=5
    )
    redis_client.ping()
except (redis.ConnectionError, AttributeError) as e:
    logger.error(f"Redis connection failed: {e}. Falling back to no blacklisting.")
    redis_client = None

class AnomalyDetector:
    def __init__(self):
        self.model = IsolationForest(contamination=0.1, random_state=42)
        self.is_trained = False

    def train(self):
        logs = AuditLog.objects.filter(action__in=["Candidate Login", "Employer Login"]).values('ip_address', 'timestamp')
        df = pd.DataFrame(logs)
        if len(df) < 10:
            return
        df['hour'] = df['timestamp'].dt.hour
        df['ip_numeric'] = df['ip_address'].apply(lambda x: int(''.join([f"{int(i):03d}" for i in x.split('.')]), 10))
        X = df[['hour', 'ip_numeric']].fillna(0)
        self.model.fit(X)
        self.is_trained = True

    def predict(self, ip_address, timestamp):
        if not self.is_trained:
            return False
        try:
            ip_numeric = int(''.join([f"{int(i):03d}" for i in ip_address.split('.')]), 10)
            hour = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").hour if isinstance(timestamp, str) else timestamp.hour
            prediction = self.model.predict([[hour, ip_numeric]])
            return prediction[0] == -1
        except (ValueError, AttributeError):
            logger.warning(f"Invalid IP or timestamp format: {ip_address}, {timestamp}")
            return False

detector = AnomalyDetector()

class CustomThrottle(UserRateThrottle):
    rate = '10/minute'

class TierPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        host = request.get_host().split(":")[0]
        if host not in ["api.einstellen.ai", "localhost"]:
            logger.error(f"Invalid host: {host}")
            return False
        
        tenant_tier = request.headers.get("X-Tenant-Tier", "TA-Copilot").lower()
        valid_tiers = ['ta-copilot', 'humanadv', 'humanpro']
        if tenant_tier not in valid_tiers:
            logger.error(f"Invalid tenant tier: {tenant_tier}")
            return False

        try:
            if tenant_tier == "ta-copilot":
                tenant, created = Tenant.objects.get_or_create(
                    tier="TA-Copilot", subdomain=None, defaults={"name": "Default TA-Copilot"}
                )
                if created or not hasattr(tenant, 'subscription'):
                    tenant.subscription = None
            else:
                subdomain = request.headers.get("X-Subdomain", tenant_tier[:3])
                tenant = Tenant.objects.get(tier=tenant_tier.capitalize(), subdomain=subdomain)
                if not hasattr(tenant, 'subscription') or not tenant.subscription.is_active:
                    logger.warning(f"Inactive or missing subscription for tenant: {tenant.name}")
                    return False
        except Tenant.DoesNotExist:
            logger.error(f"No tenant found for tier: {tenant_tier}, subdomain: {subdomain if tenant_tier != 'ta-copilot' else 'None'}")
            return False

        request.tenant = tenant

        if tenant.tier == 'TA-Copilot' and request.path.endswith("/assign-role/"):
            return False
        return True

def blacklist_token(token, expiry_seconds):
    if redis_client:
        try:
            redis_client.setex(token, expiry_seconds, "blacklisted")
            logger.info(f"Token blacklisted: {token[:10]}...")
        except redis.RedisError as e:
            logger.error(f"Failed to blacklist token: {e}")

def blacklist_email(email):
    if redis_client:
        try:
            redis_client.setex(f"blacklist_email:{email}", 86400, "blacklisted")  # 24-hour blacklist
            logger.info(f"Email blacklisted: {email}")
        except redis.RedisError as e:
            logger.error(f"Failed to blacklist email: {e}")

def check_email_blacklist(email):
    if redis_client and redis_client.get(f"blacklist_email:{email}"):
        return True
    return False

def track_device_login(user, device_id, tenant_id):
    if not redis_client:
        return
    try:
        session_key = f"session:{user.id}"
        current_device = redis_client.get(session_key)
        attempt_key = f"login_attempts:{user.email}"
        attempts = redis_client.get(attempt_key) or 0
        attempts = int(attempts)

        if current_device and current_device != device_id:
            attempts += 1
            redis_client.setex(attempt_key, 3600, attempts)
            if attempts > 3:
                blacklist_email(user.email)
                redis_client.delete(session_key)
                return False
            blacklist_token(current_device, 3600)
        redis_client.setex(session_key, 86400, device_id)
        return True
    except redis.RedisError as e:
        logger.error(f"Failed to track device login: {e}")
        return True

class CandidateSignupView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        serializer = CandidateSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        if not user:
            return Response({"message": "OTP sent to phone"}, status=status.HTTP_200_OK)

        identifier = user.phone_number
        if check_email_blacklist(identifier):
            logger.warning(f"Signup attempt with blacklisted phone: {identifier}")
            return Response(
                {"error": "Account blacklisted due to multiple device attempts"},
                status=status.HTTP_403_FORBIDDEN
            )

        ip = request.META.get("REMOTE_ADDR", "unknown")

        if not settings.DEBUG:
            detector.train()
            if detector.predict(ip, datetime.now()):
                logger.warning(f"Anomaly detected for user {user.id} from IP {ip}")
                return Response(
                    {"error": "Anomaly detected", "details": "Signup flagged as suspicious"},
                    status=status.HTTP_403_FORBIDDEN
                )

        device_id = request.headers.get("X-Device-ID", ip)
        if not track_device_login(user, device_id, str(tenant.id)):
            logger.warning(f"Multiple device signup attempts detected for user {user.id}")
            return Response(
                {"error": "Multiple device signup attempts detected"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        access_token = str(refresh.access_token)

        AuditLog.objects.create(
            user=user,
            action="Candidate Signup",
            ip_address=ip,
            tenant=tenant,
            details={"user_id": str(user.id)}
        )
        logger.info(f"Candidate signed up and authenticated: {user.phone_number}")

        return Response(
            {
                "user": UserSerializer(user).data,
                "access_token": access_token,
                "refresh_token": str(refresh),
            },
            status=status.HTTP_201_CREATED
        )

class CandidateLoginView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        serializer = CandidateLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not user:
            return Response({"detail": "OTP sent to phone"}, status=status.HTTP_200_OK)
        
        if check_email_blacklist(user.email or user.phone_number):
            return Response({"error": "Account blacklisted due to multiple device attempts"}, status=status.HTTP_403_FORBIDDEN)

        ip = request.META.get("REMOTE_ADDR", "unknown")
        if not settings.DEBUG:
            detector.train()
            if detector.predict(ip, datetime.now()):
                logger.warning(f"Anomaly detected for user {user.id} from IP {ip}")
                return Response({"error": "Anomaly detected", "details": "Login flagged as suspicious"}, status=status.HTTP_403_FORBIDDEN)
        
        device_id = request.headers.get("X-Device-ID", ip)
        if not track_device_login(user, device_id, str(tenant.id)):
            return Response({"error": "Multiple device login attempts detected"}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        AuditLog.objects.create(user=user, action="Candidate Login", ip_address=ip, tenant=tenant, details={"user_id": str(user.id)})
        logger.info(f"Candidate logged in: {user.phone_number}")
        return Response({"access_token": str(refresh.access_token), "refresh_token": str(refresh)}, status=status.HTTP_200_OK)

class EmployerSignupView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        serializer = EmployerSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        if not user:
            return Response({"message": "OTP sent to phone"}, status=status.HTTP_200_OK)
        
        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        access_token = str(refresh.access_token)
        
        AuditLog.objects.create(
            user=user, action="Employer Signup", ip_address=request.META.get("REMOTE_ADDR", "unknown"),
            tenant=tenant, details={"user_id": str(user.id)}
        )
        logger.info(f"Employer signed up: {user.username}")
        return Response(
            {
                "user": UserSerializer(user).data,
                "access_token": access_token,
                "refresh_token": str(refresh),
            },
            status=status.HTTP_201_CREATED
        ) 

class EmployerLoginView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        serializer = EmployerLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        if not user:
            return Response({"detail": "OTP sent to phone"}, status=status.HTTP_200_OK)
        
        if check_email_blacklist(user.email):
            return Response({"error": "Account blacklisted due to multiple device attempts"}, status=status.HTTP_403_FORBIDDEN)

        ip = request.META.get("REMOTE_ADDR", "unknown")
        detector.train()
        if detector.predict(ip, datetime.now()):
            logger.warning(f"Anomaly detected for user {user.id} from IP {ip}")
            return Response({"error": "Anomaly detected", "details": "Login flagged as suspicious"}, status=status.HTTP_403_FORBIDDEN)
        
        device_id = request.headers.get("X-Device-ID", ip)
        if not track_device_login(user, device_id, str(tenant.id)):
            return Response({"error": "Multiple device login attempts detected"}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        refresh["tenant_id"] = str(tenant.id)
        AuditLog.objects.create(user=user, action="Employer Login", ip_address=ip, tenant=tenant, details={"user_id": str(user.id)})
        logger.info(f"Employer logged in: {user.username}")
        return Response({"access_token": str(refresh.access_token), "refresh_token": str(refresh)}, status=status.HTTP_200_OK)

class RefreshTokenView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response({"error": "Refresh token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            refresh = RefreshToken(refresh_token)
            user = User.objects.get(id=refresh["user_id"])
            tenant = Tenant.objects.get(id=refresh["tenant_id"])
            if redis_client and redis_client.get(refresh_token):
                logger.warning(f"Blacklisted token used: {refresh_token[:10]}...")
                return Response({"error": "Token blacklisted"}, status=status.HTTP_401_UNAUTHORIZED)
            session_key = f"session:{user.id}"
            current_device = redis_client.get(session_key) if redis_client else None
            device_id = request.headers.get("X-Device-ID", request.META.get("REMOTE_ADDR", "unknown"))
            if current_device and current_device != device_id:
                return Response({"error": "Session active on another device"}, status=status.HTTP_403_FORBIDDEN)
            access_token = str(refresh.access_token)
            logger.info(f"Token refreshed for user: {user.id}")
            return Response({"access_token": access_token}, status=status.HTTP_200_OK)
        except (jwt.InvalidTokenError, User.DoesNotExist, Tenant.DoesNotExist) as e:
            logger.error(f"Refresh token error: {str(e)}")
            return Response({"error": "Invalid refresh token", "details": str(e)}, status=status.HTTP_401_UNAUTHORIZED)

class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, TierPermission]
    throttle_classes = [CustomThrottle]

    def get(self, request):
        logger.info(f"Profile accessed by user: {request.user.id}")
        return Response(UserSerializer(request.user).data, status=status.HTTP_200_OK)

class AssignRoleView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser, TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        serializer = UserRoleSerializer(data=request.data, context={'tenant': tenant})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        user = User.objects.get(id=serializer.validated_data["user"])
        role = Role.objects.get(id=serializer.validated_data["role"])
        AuditLog.objects.create(
            user=request.user, 
            action="Assign Role", 
            ip_address=request.META.get("REMOTE_ADDR", "unknown"),
            tenant=tenant, 
            details={"user_id": str(user.id), "role_id": str(role.id)}
        )
        logger.info(f"Role assigned by {request.user.id} to user {user.id}")
        return Response({"message": "Role assigned"}, status=status.HTTP_201_CREATED)

class SetupMFAView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        user = request.user
        tenant = request.tenant
        device, created = TOTPDevice.objects.get_or_create(user=user, name="default")
        if created:
            qr = qrcode.make(device.config_url)
            buffered = BytesIO()
            qr.save(buffered, format="PNG")
            qr_code_url = "data:image/png;base64," + base64.b64encode(buffered.getvalue()).decode()
            AuditLog.objects.create(user=user, action="Setup MFA", ip_address=request.META.get("REMOTE_ADDR", "unknown"), tenant=tenant, details={"user_id": str(user.id)})
            logger.info(f"MFA setup for user: {user.id}")
            return Response({"qr_code_url": qr_code_url}, status=status.HTTP_200_OK)
        return Response({"message": "MFA already set up"}, status=status.HTTP_400_BAD_REQUEST)

class VerifyMFAView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        user = request.user
        tenant = request.tenant
        totp_code = request.data.get("totp_code")
        if not totp_code:
            return Response({"error": "TOTP code required"}, status=status.HTTP_400_BAD_REQUEST)
        for device in devices_for_user(user):
            if device.verify_token(totp_code):
                AuditLog.objects.create(user=user, action="Verify MFA", ip_address=request.META.get("REMOTE_ADDR", "unknown"), tenant=tenant, details={"user_id": str(user.id)})
                logger.info(f"MFA verified for user: {user.id}")
                return Response({"message": "MFA verified"}, status=status.HTTP_200_OK)
        logger.warning(f"Invalid MFA attempt for user: {user.id}")
        return Response({"error": "Invalid TOTP code"}, status=status.HTTP_401_UNAUTHORIZED)

class SocialLoginView(APIView):
    permission_classes = [TierPermission]
    throttle_classes = [CustomThrottle]

    def post(self, request):
        tenant = request.tenant
        provider = request.data.get("provider")
        access_token = request.data.get("access_token")
        if not provider or not access_token:
            return Response({"error": "Provider and access_token required"}, status=status.HTTP_400_BAD_REQUEST)
        if provider == "google-oauth2":
            backend = GoogleOAuth2()
            for attempt in range(3):
                try:
                    user_data = backend.user_data(access_token)
                    if not user_data or "email" not in user_data:
                        return Response({"error": "Invalid token or missing email"}, status=status.HTTP_401_UNAUTHORIZED)
                    break
                except HTTPError as e:
                    sleep(2 ** attempt)
                    if attempt == 2:
                        logger.error(f"Google OAuth failed after retries: {str(e)}")
                        return Response({"error": f"Failed to validate token: {str(e)}"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            email = user_data["email"]
            full_name = user_data.get("name", email.split("@")[0])
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create_user(
                    email=email,
                    phone_number=email.split("@")[0] + "@temp",
                    full_name=full_name,
                    password=None
                )
            if check_email_blacklist(user.email):
                return Response({"error": "Account blacklisted due to multiple device attempts"}, status=status.HTTP_403_FORBIDDEN)
            device_id = request.headers.get("X-Device-ID", request.META.get("REMOTE_ADDR", "unknown"))
            if not track_device_login(user, device_id, str(tenant.id)):
                return Response({"error": "Multiple device login attempts detected"}, status=status.HTTP_403_FORBIDDEN)
            refresh = RefreshToken.for_user(user)
            refresh["tenant_id"] = str(tenant.id)
            AuditLog.objects.create(user=user, action="Social Login (Google)", ip_address=request.META.get("REMOTE_ADDR", "unknown"), tenant=tenant, details={"user_id": str(user.id)})
            logger.info(f"Social login (Google) for user: {user.email}")
            return Response({"access_token": str(refresh.access_token), "refresh_token": str(refresh)}, status=status.HTTP_200_OK)
        return Response({"error": "Unsupported provider"}, status=status.HTTP_400_BAD_REQUEST)
    

class VerifyTokenView(APIView):
    def post(self, request):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return Response({"error": "No token provided"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            access_token = AccessToken(token)
            payload = access_token.payload
            user_id = payload.get('user_id')
            tenant_id = payload.get('tenant_id')
            if not user_id or not tenant_id:
                raise ValueError("Missing user_id or tenant_id in token")
            return Response({"user_id": user_id, "tenant_id": tenant_id}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.warning(f"Token verification failed: {e}")
            return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)