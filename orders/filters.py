import django_filters
from django.db.models import Q
from django.utils import timezone

from .models import CustomerSubscription, Order


class OrderFilter(django_filters.FilterSet):
    order_status = django_filters.CharFilter(field_name='order_status')
    order_month = django_filters.CharFilter(field_name='order_month')
    meal_type = django_filters.CharFilter(field_name='meal_type_snapshot')
    activity = django_filters.ChoiceFilter(
        choices=(('active', 'Active'), ('inactive', 'Inactive')),
        method='filter_activity',
    )
    created_after = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='gte')
    created_before = django_filters.IsoDateTimeFilter(field_name='created_at', lookup_expr='lte')
    start_date = django_filters.DateFilter(field_name='order_start_date', lookup_expr='gte')
    end_date = django_filters.DateFilter(field_name='order_end_date', lookup_expr='lte')

    class Meta:
        model = Order
        fields = [
            'order_status',
            'order_month',
            'meal_type',
            'activity',
            'created_after',
            'created_before',
            'start_date',
            'end_date',
        ]

    def filter_activity(self, queryset, name, value):
        today = timezone.localdate()
        if value == 'active':
            return queryset.filter(
                order_status__in={Order.OrderStatus.CONFIRMED, Order.OrderStatus.ACTIVE},
                order_start_date__lte=today,
                order_end_date__gte=today,
            )
        if value == 'inactive':
            return queryset.filter(
                Q(order_status__in={Order.OrderStatus.COMPLETED, Order.OrderStatus.CANCELLED})
                | Q(order_end_date__lt=today)
                | Q(order_start_date__gt=today)
            )
        return queryset


class CustomerSubscriptionFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=CustomerSubscription.Status.choices)
    plan_public_id = django_filters.UUIDFilter(field_name='meal__public_id')
    started_after = django_filters.DateFilter(field_name='started_on', lookup_expr='gte')
    started_before = django_filters.DateFilter(field_name='started_on', lookup_expr='lte')
    cancelled_after = django_filters.IsoDateTimeFilter(
        field_name='cancelled_at', lookup_expr='gte'
    )
    cancelled_before = django_filters.IsoDateTimeFilter(
        field_name='cancelled_at', lookup_expr='lte'
    )

    class Meta:
        model = CustomerSubscription
        fields = [
            'status',
            'plan_public_id',
            'started_after',
            'started_before',
            'cancelled_after',
            'cancelled_before',
        ]
