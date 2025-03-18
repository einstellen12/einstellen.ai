import logging
from django.core.mail import send_mail
from django.conf import settings
from logging.handlers import SMTPHandler
from django.core.exceptions import ImproperlyConfigured

recipient_list = settings.RECIPIENT_LIST

class EmailErrorHandler(SMTPHandler):
    def emit(self, record):
        if record.levelno < logging.ERROR:
            return
        try:
            msg = self.format(record)
            send_mail(
                subject=f"Billing Service {record.levelname}: {record.module}",
                message=msg,
                from_email=settings.EMAIL_HOST_USER,
                recipient_list=recipient_list,
                fail_silently=True,
            )
        except Exception as e:
            print(f"Failed to send error email: {e}")

def setup_logger():
    required_settings = ['EMAIL_HOST', 'EMAIL_PORT', 'EMAIL_HOST_USER', 'EMAIL_HOST_PASSWORD']
    for setting in required_settings:
        if not hasattr(settings, setting):
            raise ImproperlyConfigured(f"Missing email setting: {setting}")

    logger = logging.getLogger('billing_service')
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(console_handler)

    email_handler = EmailErrorHandler(
        mailhost=(settings.EMAIL_HOST, settings.EMAIL_PORT),
        fromaddr=settings.EMAIL_HOST_USER,
        toaddrs=recipient_list,
        subject='Billing Service Error/Critical',
        credentials=(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD),
        secure=() if settings.EMAIL_USE_TLS else None
    )
    email_handler.setLevel(logging.ERROR)
    email_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d'))
    logger.addHandler(email_handler)

    return logger

logger = setup_logger()