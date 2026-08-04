import django_filters
from django.db.models import Q

from user_management.models import RiderProfile


class RiderProfileFilter(django_filters.FilterSet):
    approval_status = django_filters.ChoiceFilter(choices=RiderProfile.ApprovalStatus.choices)
    is_email_verified = django_filters.BooleanFilter()
    is_verified = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = RiderProfile
        fields = ['approval_status', 'is_email_verified', 'is_verified']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(user__email__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
            | Q(phone__icontains=value)
        )
