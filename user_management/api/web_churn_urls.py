from django.urls import path

from user_management.api.admin_churn_views import (
    AdminChurnAnalyticsView,
    AdminChurnCustomersView,
    AdminChurnFollowUpViewSet,
)

app_name = 'web_churn'

follow_ups = AdminChurnFollowUpViewSet.as_view(
    {
        'get': 'list',
        'post': 'create',
    }
)
follow_up_detail = AdminChurnFollowUpViewSet.as_view(
    {
        'get': 'retrieve',
        'patch': 'partial_update',
    }
)

urlpatterns = [
    path('customers/', AdminChurnCustomersView.as_view(), name='customers'),
    path('analytics/', AdminChurnAnalyticsView.as_view(), name='analytics'),
    path('follow-ups/', follow_ups, name='follow-ups'),
    path('follow-ups/<uuid:public_id>/', follow_up_detail, name='follow-up-detail'),
]
