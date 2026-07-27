from django.urls import include, path, re_path
from rest_framework.routers import DefaultRouter

from .views import (
    WalletDetailView,
    WalletRechargeView,
    WalletTransactionViewSet,
    WalletWithdrawView,
)

app_name = 'wallet'

router = DefaultRouter()
router.register('transactions', WalletTransactionViewSet, basename='wallet-transaction')

# Frontend POSTs may omit trailing slash; APPEND_SLASH cannot safely redirect POST.
recharge = WalletRechargeView.as_view()
withdraw = WalletWithdrawView.as_view()

urlpatterns = [
    path('', WalletDetailView.as_view(), name='wallet-detail'),
    path('recharge/', recharge, name='wallet-recharge'),
    path('withdraw/', withdraw, name='wallet-withdraw'),
    re_path(r'^recharge$', recharge, name='wallet-recharge-noslash'),
    re_path(r'^withdraw$', withdraw, name='wallet-withdraw-noslash'),
    path('', include(router.urls)),
]
