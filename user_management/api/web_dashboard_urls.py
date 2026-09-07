from django.urls import path

from user_management.api.admin_dashboard_views import AdminDashboardSummaryView

app_name = 'web_admin_dashboard'

urlpatterns = [
    path('summary/', AdminDashboardSummaryView.as_view(), name='summary'),
]
