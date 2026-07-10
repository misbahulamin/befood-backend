from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WalletViewSet, WalletTransactionViewSet, TopUpRequestViewSet, WalletPaymentViewSet
router = DefaultRouter()
router.register(r'wallet', WalletViewSet)
router.register(r'wallettransaction', WalletTransactionViewSet)
router.register(r'topuprequest', TopUpRequestViewSet)
router.register(r'walletpayment', WalletPaymentViewSet)
urlpatterns = [path("", include(router.urls))]