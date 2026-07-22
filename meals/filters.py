import django_filters

from meals.models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine


class MealCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    meal_type = django_filters.ChoiceFilter(choices=MealCategory.MealType.choices)
    search = django_filters.CharFilter(field_name='meal_name', lookup_expr='icontains')

    class Meta:
        model = MealCategory
        fields = ['is_active', 'meal_type', 'search']


class IngredientFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    product_role = django_filters.ChoiceFilter(choices=Ingredient.ProductRole.choices)
    search = django_filters.CharFilter(field_name='name', lookup_expr='icontains')

    class Meta:
        model = Ingredient
        fields = ['is_active', 'product_role', 'search']


class MealCycleFilter(django_filters.FilterSet):
    year = django_filters.NumberFilter()
    month = django_filters.NumberFilter()

    class Meta:
        model = MealCycle
        fields = ['year', 'month']


class MealCyclePlanFilter(django_filters.FilterSet):
    cycle = django_filters.NumberFilter(field_name='cycle_id')
    meal_category = django_filters.NumberFilter(field_name='meal_category_id')
    status = django_filters.ChoiceFilter(choices=MealCyclePlan.Status.choices)
    year = django_filters.NumberFilter(field_name='cycle__year')
    month = django_filters.NumberFilter(field_name='cycle__month')

    class Meta:
        model = MealCyclePlan
        fields = ['cycle', 'meal_category', 'status', 'year', 'month']


class MealCyclePlanLineFilter(django_filters.FilterSet):
    plan = django_filters.NumberFilter(field_name='plan_id')
    ingredient = django_filters.NumberFilter(field_name='ingredient_id')

    class Meta:
        model = MealCyclePlanLine
        fields = ['plan', 'ingredient']
