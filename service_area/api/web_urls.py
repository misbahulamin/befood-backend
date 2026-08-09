from django.urls import path

from service_area.api.views import (
    ServiceAreaAdminAnalyticsView,
    ServiceAreaAdminDetailView,
    ServiceAreaAdminListCreateView,
    ServiceAreaAdminRequestListView,
    ServiceAreaAdminStatusView,
)

app_name = 'web_service_area'

urlpatterns = [
    path('', ServiceAreaAdminListCreateView.as_view(), name='list-create'),
    path(
        'requests/',
        ServiceAreaAdminRequestListView.as_view(),
        name='requests',
    ),
    path(
        'requests/summary/',
        ServiceAreaAdminAnalyticsView.as_view(),
        name='requests-summary',
    ),
    path(
        '<uuid:public_id>/',
        ServiceAreaAdminDetailView.as_view(),
        name='detail',
    ),
    path(
        '<uuid:public_id>/status/',
        ServiceAreaAdminStatusView.as_view(),
        name='status',
    ),
]
