"""
ASGI config for yakunin_service project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/stable/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

# early init for django app
django_app = get_asgi_application()

import yakunin_service.routing  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "yakunin_service.settings")

application = ProtocolTypeRouter(
    {
        "http": django_app,
        "websocket": AllowedHostsOriginValidator(URLRouter(yakunin_service.routing.websocket_urlpatterns)),
    },
)
