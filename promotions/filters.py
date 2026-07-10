import django_filters
from .models import Coupon
class CouponFilter(django_filters.FilterSet):
    class Meta: model = Coupon; fields = ['is_active','code']
