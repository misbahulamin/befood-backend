import django_filters
from django.db.models import Q

from faqs.models import FaqQuestion, FaqType


class FaqTypeFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = FaqType
        fields = ['is_active', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(Q(name__icontains=value))


class FaqQuestionFilter(django_filters.FilterSet):
    is_published = django_filters.BooleanFilter()
    type_public_id = django_filters.UUIDFilter(field_name='type__public_id')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = FaqQuestion
        fields = ['is_published', 'type_public_id', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(question__icontains=value) | Q(answer__icontains=value)
        )
