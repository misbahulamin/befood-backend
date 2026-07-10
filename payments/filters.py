import django_filters
from .models import PaymentIntent
class PaymentIntentFilter(django_filters.FilterSet):
    class Meta: model = PaymentIntent; fields = ['status','method']
