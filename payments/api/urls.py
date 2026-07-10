from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PaymentMethodViewSet, PaymentIntentViewSet, PaymentTransactionViewSet, PaymentWebhookLogViewSet, RefundViewSet
router = DefaultRouter()
router.register(r'paymentmethod', PaymentMethodViewSet)
router.register(r'paymentintent', PaymentIntentViewSet)
router.register(r'paymenttransaction', PaymentTransactionViewSet)
router.register(r'paymentwebhooklog', PaymentWebhookLogViewSet)
router.register(r'refund', RefundViewSet)
urlpatterns = [path("", include(router.urls))]