from django.urls import path

from admin_wallet.api.profit_views import AdminProfitDashboardView, AdminProfitHistoryView

app_name = 'web_admin_profit'

urlpatterns = [
    path('dashboard/', AdminProfitDashboardView.as_view(), name='dashboard'),
    path('history/', AdminProfitHistoryView.as_view(), name='history'),
]
