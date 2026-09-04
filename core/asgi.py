import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

from core.load_env import load_project_env

load_project_env()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

django_asgi_app = get_asgi_application()

from support.realtime.middleware import TokenAuthMiddlewareStack  # noqa: E402
from support.realtime.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        'http': django_asgi_app,
        'websocket': AllowedHostsOriginValidator(
            TokenAuthMiddlewareStack(
                URLRouter(websocket_urlpatterns),
            ),
        ),
    },
)
