"""
ASGI config for ta_copilot project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
import interview.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ta_copilot.settings')

import django
django.setup()

def get_application():
    import interview.routing
    return ProtocolTypeRouter({
        "http": get_asgi_application(),
        "websocket": URLRouter(interview.routing.websocket_urlpatterns),
    })

application = get_application()