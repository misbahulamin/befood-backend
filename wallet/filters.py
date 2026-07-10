import django_filters
from .models import WalletTransaction
class WalletTransactionFilter(django_filters.FilterSet):
    class Meta: model = WalletTransaction; fields = ['type']
