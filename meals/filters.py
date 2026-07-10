import django_filters

from meals.models import MealCategory


class MealCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    meal_type = django_filters.ChoiceFilter(choices=MealCategory.MealType.choices)
    search = django_filters.CharFilter(field_name='meal_name', lookup_expr='icontains')

    class Meta:
        model = MealCategory
        fields = ['is_active', 'meal_type', 'search']
