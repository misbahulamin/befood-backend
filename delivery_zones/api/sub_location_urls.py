from django.urls import path

from delivery_zones.api.web_views import (
    DeliverySubLocationDetailView,
    DeliverySubLocationListCreateView,
)

app_name = 'web_delivery_sub_locations'

urlpatterns = [
    path('', DeliverySubLocationListCreateView.as_view(), name='list-create'),
    path('<uuid:public_id>/', DeliverySubLocationDetailView.as_view(), name='detail'),
]
