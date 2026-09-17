from django.urls import path

from delivery_zones.api.web_views import (
    DeliveryLocationDetailView,
    DeliveryLocationListCreateView,
)

app_name = 'web_delivery_locations'

urlpatterns = [
    path('', DeliveryLocationListCreateView.as_view(), name='list-create'),
    path('<uuid:public_id>/', DeliveryLocationDetailView.as_view(), name='detail'),
]
