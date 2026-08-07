from django.urls import path

from onahar.api.views import (
    OnaharAdminAuditLogView,
    OnaharAdminDistributionCancelView,
    OnaharAdminDistributionDetailView,
    OnaharAdminDistributionListCreateView,
    OnaharAdminDistributionMediaView,
    OnaharAdminDistributionPublishView,
    OnaharAdminFundView,
    OnaharAdminSettingsView,
    OnaharAdminTargetHistoryView,
)

app_name = 'web_onahar'

urlpatterns = [
    path('settings/', OnaharAdminSettingsView.as_view(), name='settings'),
    path('settings/history/', OnaharAdminTargetHistoryView.as_view(), name='settings-history'),
    path('fund/', OnaharAdminFundView.as_view(), name='fund'),
    path('audit-logs/', OnaharAdminAuditLogView.as_view(), name='audit-logs'),
    path('distributions/', OnaharAdminDistributionListCreateView.as_view(), name='distributions'),
    path(
        'distributions/<uuid:public_id>/',
        OnaharAdminDistributionDetailView.as_view(),
        name='distribution-detail',
    ),
    path(
        'distributions/<uuid:public_id>/publish/',
        OnaharAdminDistributionPublishView.as_view(),
        name='distribution-publish',
    ),
    path(
        'distributions/<uuid:public_id>/cancel/',
        OnaharAdminDistributionCancelView.as_view(),
        name='distribution-cancel',
    ),
    path(
        'distributions/<uuid:public_id>/media/',
        OnaharAdminDistributionMediaView.as_view(),
        name='distribution-media',
    ),
]
