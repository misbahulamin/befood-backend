from django.urls import path

from admin_wallet.api.views import (
    AdminWalletAuditLogListView,
    AdminWalletDashboardView,
    AdminWalletDepositView,
    AdminWalletExpenseView,
    AdminWalletSummaryView,
    AdminWalletTransactionDetailView,
    AdminWalletTransactionListView,
    AdminWalletWithdrawalView,
)

app_name = 'web_admin_wallet'

urlpatterns = [
    path('', AdminWalletSummaryView.as_view(), name='summary'),
    path('dashboard/', AdminWalletDashboardView.as_view(), name='dashboard'),
    path('transactions/', AdminWalletTransactionListView.as_view(), name='transactions'),
    path(
        'transactions/<uuid:public_id>/',
        AdminWalletTransactionDetailView.as_view(),
        name='transaction-detail',
    ),
    path('deposits/', AdminWalletDepositView.as_view(), name='deposits'),
    path('withdrawals/', AdminWalletWithdrawalView.as_view(), name='withdrawals'),
    path('expenses/', AdminWalletExpenseView.as_view(), name='expenses'),
    path('audit-logs/', AdminWalletAuditLogListView.as_view(), name='audit-logs'),
]
