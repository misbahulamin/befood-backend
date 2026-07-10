import django_filters

from .models import Order


class OrderFilter(django_filters.FilterSet):
    order_status = django_filters.CharFilter(field_name='order_status')
    order_month = django_filters.CharFilter(field_name='order_month')
    meal_type = django_filters.CharFilter(field_name='meal_type_snapshot')

    class Meta:
        model = Order
        fields = ['order_status', 'order_month', 'meal_type_snapshot']
