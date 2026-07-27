import django_filters
from django.db.models import Q

from assets.models import AssetCategory, PermanentAsset


class AssetCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    include_inactive = django_filters.BooleanFilter(
        method='filter_include_inactive',
        label='Include inactive',
    )
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = AssetCategory
        fields = ['is_active', 'include_inactive', 'search']

    def filter_include_inactive(self, queryset, name, value):
        # Handled in view get_queryset; keep filter for OpenAPI discovery.
        return queryset

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(description__icontains=value)
        )


class PermanentAssetFilter(django_filters.FilterSet):
    status = django_filters.ChoiceFilter(choices=PermanentAsset.Status.choices)
    is_active = django_filters.BooleanFilter()
    include_inactive = django_filters.BooleanFilter(
        method='filter_include_inactive',
        label='Include inactive',
    )
    category_public_id = django_filters.UUIDFilter(
        field_name='category__public_id',
    )
    outlet = django_filters.NumberFilter(field_name='outlet_id')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = PermanentAsset
        fields = [
            'status',
            'is_active',
            'include_inactive',
            'category_public_id',
            'outlet',
            'search',
        ]

    def filter_include_inactive(self, queryset, name, value):
        return queryset

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(asset_tag__icontains=value)
            | Q(serial_number__icontains=value)
            | Q(brand__icontains=value)
            | Q(model__icontains=value)
        )
