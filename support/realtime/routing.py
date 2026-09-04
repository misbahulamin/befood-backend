from django.urls import path

from support.realtime.consumers import SupportConversationConsumer

websocket_urlpatterns = [
    path(
        'ws/support/<uuid:conversation_public_id>/',
        SupportConversationConsumer.as_asgi(),
    ),
]
