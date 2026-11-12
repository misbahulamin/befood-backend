from django.urls import path

from support.realtime.consumers import SupportAdminInboxConsumer, SupportConversationConsumer

websocket_urlpatterns = [
    path('ws/support/inbox/', SupportAdminInboxConsumer.as_asgi()),
    path(
        'ws/support/<uuid:conversation_public_id>/',
        SupportConversationConsumer.as_asgi(),
    ),
]
