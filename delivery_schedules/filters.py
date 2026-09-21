import django_filters
from django.db.models import Q

from delivery_schedules.models import DeliverySchedule


class DeliveryScheduleFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = DeliverySchedule
        fields = ['is_active', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value))
