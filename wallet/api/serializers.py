from rest_framework import serializers
from wallet.models import Wallet, WalletTransaction, TopUpRequest, WalletPayment

class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = "__all__"

class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = "__all__"

class TopUpRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopUpRequest
        fields = "__all__"

class WalletPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletPayment
        fields = "__all__"
