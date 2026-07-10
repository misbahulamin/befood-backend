from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from wallet.models import Wallet, WalletTransaction, TopUpRequest, WalletPayment
from .serializers import WalletSerializer, WalletTransactionSerializer, TopUpRequestSerializer, WalletPaymentSerializer

class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    permission_classes = [IsAuthenticated]

class WalletTransactionViewSet(viewsets.ModelViewSet):
    queryset = WalletTransaction.objects.all()
    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]

class TopUpRequestViewSet(viewsets.ModelViewSet):
    queryset = TopUpRequest.objects.all()
    serializer_class = TopUpRequestSerializer
    permission_classes = [IsAuthenticated]

class WalletPaymentViewSet(viewsets.ModelViewSet):
    queryset = WalletPayment.objects.all()
    serializer_class = WalletPaymentSerializer
    permission_classes = [IsAuthenticated]
