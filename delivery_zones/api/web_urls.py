from django.urls import path

from delivery_zones.api.web_views import (
    DeliveryZoneAssignRiderView,
    DeliveryZoneDeactivateView,
    DeliveryZoneDetailView,
    DeliveryZoneListCreateView,
    DeliveryZoneOpsSummaryView,
)

app_name = 'web_delivery_zones'

urlpatterns = [
    path('ops/summary/', DeliveryZoneOpsSummaryView.as_view(), name='ops-summary'),
    path('', DeliveryZoneListCreateView.as_view(), name='zone-list-create'),
    path(
        '<uuid:public_id>/',
        DeliveryZoneDetailView.as_view(),
        name='zone-detail',
    ),
    path(
        '<uuid:public_id>/assign-delivery-man/',
        DeliveryZoneAssignRiderView.as_view(),
        name='zone-assign-rider',
    ),
    path(
        '<uuid:public_id>/deactivate/',
        DeliveryZoneDeactivateView.as_view(),
        name='zone-deactivate',
    ),
]
