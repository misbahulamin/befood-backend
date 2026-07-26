import django_filters
from django.db.models import Q

from notices.models import Notice


class NoticeFilter(django_filters.FilterSet):
    is_published = django_filters.BooleanFilter()
    severity = django_filters.ChoiceFilter(choices=Notice.Severity.choices)
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = Notice
        fields = ['is_published', 'severity', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title_en__icontains=value)
            | Q(title_bn__icontains=value)
            | Q(body_en__icontains=value)
            | Q(body_bn__icontains=value)
        )
