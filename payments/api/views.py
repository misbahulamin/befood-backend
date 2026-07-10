from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from payments.models import PaymentMethod, PaymentIntent, PaymentTransaction, PaymentWebhookLog, Refund
from .serializers import PaymentMethodSerializer, PaymentIntentSerializer, PaymentTransactionSerializer, PaymentWebhookLogSerializer, RefundSerializer

class PaymentMethodViewSet(viewsets.ModelViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
    permission_classes = [IsAuthenticated]

class PaymentIntentViewSet(viewsets.ModelViewSet):
    queryset = PaymentIntent.objects.all()
    serializer_class = PaymentIntentSerializer
    permission_classes = [IsAuthenticated]

class PaymentTransactionViewSet(viewsets.ModelViewSet):
    queryset = PaymentTransaction.objects.all()
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]

class PaymentWebhookLogViewSet(viewsets.ModelViewSet):
    queryset = PaymentWebhookLog.objects.all()
    serializer_class = PaymentWebhookLogSerializer
    permission_classes = [IsAuthenticated]

class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.all()
    serializer_class = RefundSerializer
    permission_classes = [IsAuthenticated]
