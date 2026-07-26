import django_filters
from django.db.models import Q

from announcements.models import Announcement


class AnnouncementFilter(django_filters.FilterSet):
    is_published = django_filters.BooleanFilter()
    type = django_filters.ChoiceFilter(choices=Announcement.AnnouncementType.choices)
    severity = django_filters.ChoiceFilter(choices=Announcement.Severity.choices)
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = Announcement
        fields = ['is_published', 'type', 'severity', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(description__icontains=value)
        )
