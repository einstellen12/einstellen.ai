from rest_framework import serializers
from .models import User, Role, UserRole, Tenant
from django.core.cache import cache
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
from django.conf import settings
import os
import random
import string

IS_PRODUCTION = os.getenv("DJANGO_ENV", "development") == "production"

def generate_otp(length=6):
    return ''.join(random.choices(string.digits, k=length))

class CandidateSignupSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    full_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    otp = serializers.CharField(max_length=6, required=False)

    def validate_phone_number(self, value):
        if not value.startswith("+") or len(value) < 10:
            raise serializers.ValidationError("Invalid phone number format (e.g., +1234567890)")
        return value

    def validate(self, data):
        phone_number = data["phone_number"]
        if User.objects.filter(phone_number=phone_number).exists() and "otp" not in data:
            raise serializers.ValidationError("User already exists; please log in")
        return data

    def save(self):
        phone_number = self.validated_data["phone_number"]
        full_name = self.validated_data.get("full_name", "")
        
        if "otp" not in self.validated_data:
            otp = "123456" if not IS_PRODUCTION else generate_otp()
            if IS_PRODUCTION and settings.TWILIO_PHONE:
                try:
                    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
                    client.messages.create(
                        body=f"Your OTP is {otp}",
                        from_=settings.TWILIO_PHONE,
                        to=phone_number
                    )
                except TwilioRestException as e:
                    raise serializers.ValidationError(f"Failed to send OTP: {str(e)}")
            cache.set(f"otp_{phone_number}", otp, timeout=300)
            return None
        
        otp = self.validated_data["otp"]
        cached_otp = cache.get(f"otp_{phone_number}")
        if not cached_otp or otp != cached_otp:
            raise serializers.ValidationError("Invalid OTP")
        user = User.objects.create_user(phone_number=phone_number, full_name=full_name)
        return user

class CandidateLoginSerializer(serializers.Serializer):
    phone_number = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6, required=False)

    def validate_phone_number(self, value):
        if not User.objects.filter(phone_number=value).exists():
            raise serializers.ValidationError("User does not exist")
        return value

    def validate(self, data):
        phone_number = data["phone_number"]
        if "otp" not in data:
            otp = "654321" if not IS_PRODUCTION else generate_otp()
            if IS_PRODUCTION and settings.TWILIO_PHONE:
                try:
                    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
                    client.messages.create(
                        body=f"Your OTP is {otp}",
                        from_=settings.TWILIO_PHONE,
                        to=phone_number
                    )
                except TwilioRestException as e:
                    raise serializers.ValidationError(f"Failed to send OTP: {str(e)}")
            cache.set(f"otp_{phone_number}", otp, timeout=300)
            return {"user": None}
        
        otp = data["otp"]
        cached_otp = cache.get(f"otp_{phone_number}")
        if not cached_otp or otp != cached_otp:
            raise serializers.ValidationError("Invalid OTP")
        user = User.objects.get(phone_number=phone_number)
        return {"user": user}

class EmployerSignupSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone_number = serializers.CharField(max_length=15)
    company_name = serializers.CharField(max_length=255)
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    otp = serializers.CharField(max_length=6, required=False)

    def validate_phone_number(self, value):
        if not value.startswith("+") or len(value) < 10:
            raise serializers.ValidationError("Invalid phone number format (e.g., +1234567890)")
        return value

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError("Passwords do not match")
        phone_number = data["phone_number"]
        if User.objects.filter(phone_number=phone_number).exists() and "otp" not in data:
            raise serializers.ValidationError("User already exists; please log in")
        return data

    def save(self):
        if "otp" not in self.validated_data:
            otp = "789123" if not IS_PRODUCTION else generate_otp()
            if IS_PRODUCTION and settings.TWILIO_PHONE:
                try:
                    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
                    client.messages.create(
                        body=f"Your OTP is {otp}",
                        from_=settings.TWILIO_PHONE,
                        to=self.validated_data["phone_number"]
                    )
                except TwilioRestException as e:
                    raise serializers.ValidationError(f"Failed to send OTP: {str(e)}")
            cache.set(f"otp_{self.validated_data['phone_number']}", otp, timeout=300)
            return None
        
        otp = self.validated_data["otp"]
        cached_otp = cache.get(f"otp_{self.validated_data['phone_number']}")
        if not cached_otp or otp != cached_otp:
            raise serializers.ValidationError("Invalid OTP")
        user = User.objects.create_user(
            phone_number=self.validated_data["phone_number"],
            full_name=self.validated_data["full_name"],
            username=self.validated_data["username"],
            email=self.validated_data["email"],
            company_name=self.validated_data["company_name"],
            password=self.validated_data["password"]
        )
        return user

class EmployerLoginSerializer(serializers.Serializer):
    login_field = serializers.CharField()
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(max_length=6, required=False)

    def validate_login_field(self, value):
        if "@" in value:
            if not User.objects.filter(email=value).exists():
                raise serializers.ValidationError("User does not exist")
        else:
            if not User.objects.filter(phone_number=value).exists():
                raise serializers.ValidationError("User does not exist")
        return value

    def validate(self, data):
        login_field = data["login_field"]
        password = data["password"]
        user = User.objects.filter(email=login_field).first() or User.objects.filter(phone_number=login_field).first()
        if not user or not user.check_password(password):
            raise serializers.ValidationError("Invalid credentials")
        if "otp" not in data:
            otp = "456789" if not IS_PRODUCTION else generate_otp()
            if IS_PRODUCTION and settings.TWILIO_PHONE:
                try:
                    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
                    client.messages.create(
                        body=f"Your OTP is {otp}",
                        from_=settings.TWILIO_PHONE,
                        to=user.phone_number
                    )
                except TwilioRestException as e:
                    raise serializers.ValidationError(f"Failed to send OTP: {str(e)}")
            cache.set(f"otp_{user.phone_number}", otp, timeout=300)
            return {"user": None}
        
        otp = data["otp"]
        cached_otp = cache.get(f"otp_{user.phone_number}")
        if not cached_otp or otp != cached_otp:
            raise serializers.ValidationError("Invalid OTP")
        return {"user": user}

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "phone_number", "full_name", "username", "email", "company_name"]

class UserRoleSerializer(serializers.Serializer):
    user = serializers.UUIDField()
    role = serializers.UUIDField()

    def validate(self, data):
        tenant = self.context["tenant"]
        if not User.objects.filter(id=data["user"]).exists():
            raise serializers.ValidationError("User does not exist")
        if not Role.objects.filter(id=data["role"], tenant=tenant).exists():
            raise serializers.ValidationError("Role does not exist or does not belong to this tenant")
        return data

    def save(self):
        UserRole.objects.create(
            user_id=self.validated_data["user"],
            role_id=self.validated_data["role"],
            tenant=self.context["tenant"]
        )