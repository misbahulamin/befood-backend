from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from meals.models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine
from meals.services.cycle_calculations import resolve_cost_per_customer


class IngredientSerializer(serializers.ModelSerializer):
    resolved_cost_per_customer = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = (
            'id',
            'public_id',
            'name',
            'price_per_kg',
            'customers_per_kg',
            'cost_per_customer',
            'resolved_cost_per_customer',
            'pieces_per_kg',
            'product_role',
            'is_active',
            'notes',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'public_id', 'resolved_cost_per_customer', 'created_at', 'updated_at')

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_resolved_cost_per_customer(self, obj):
        try:
            return str(resolve_cost_per_customer(obj))
        except Exception:
            return None

    def validate_name(self, value):
        return value.strip()

    def validate_pieces_per_kg(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError('Pieces per kg must be greater than 0 when provided.')
        return value

    def validate(self, attrs):
        instance = self.instance
        price = attrs['price_per_kg'] if 'price_per_kg' in attrs else getattr(instance, 'price_per_kg', None)
        customers = (
            attrs['customers_per_kg']
            if 'customers_per_kg' in attrs
            else getattr(instance, 'customers_per_kg', None)
        )
        flat_cost = (
            attrs['cost_per_customer']
            if 'cost_per_customer' in attrs
            else getattr(instance, 'cost_per_customer', None)
        )

        has_price = price is not None
        has_customers = customers is not None
        if has_price != has_customers:
            raise serializers.ValidationError(
                {
                    'price_per_kg': 'Provide both price_per_kg and customers_per_kg, or neither.',
                    'customers_per_kg': 'Provide both price_per_kg and customers_per_kg, or neither.',
                }
            )
        if has_price and price <= Decimal('0'):
            raise serializers.ValidationError({'price_per_kg': 'Price per kg must be greater than 0.'})
        if has_customers and customers <= Decimal('0'):
            raise serializers.ValidationError(
                {'customers_per_kg': 'Customers per kg must be greater than 0.'}
            )
        if not (has_price and has_customers) and flat_cost is None:
            raise serializers.ValidationError(
                {
                    'cost_per_customer': (
                        'Provide kg pricing (price_per_kg and customers_per_kg) '
                        'or a flat cost_per_customer.'
                    )
                }
            )
        if flat_cost is not None and flat_cost <= Decimal('0'):
            raise serializers.ValidationError(
                {'cost_per_customer': 'Cost per customer must be greater than 0 when provided.'}
            )
        return attrs


class MealCycleSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCycle
        fields = (
            'id',
            'public_id',
            'year',
            'month',
            'cycle_days',
            'total_meals',
            'notes',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'public_id', 'cycle_days', 'total_meals', 'created_at', 'updated_at')

    def validate_year(self, value):
        if value < 2000 or value > 2100:
            raise serializers.ValidationError('Year must be between 2000 and 2100.')
        return value

    def validate_month(self, value):
        if value < 1 or value > 12:
            raise serializers.ValidationError('Month must be between 1 and 12.')
        return value

    def validate(self, attrs):
        year = attrs.get('year') or getattr(self.instance, 'year', None)
        month = attrs.get('month') or getattr(self.instance, 'month', None)
        if year and month:
            qs = MealCycle.objects.filter(year=year, month=month)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'month': 'A meal cycle already exists for this year and month.'}
                )
        return attrs


class MealCategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCategory
        fields = ('id', 'public_id', 'meal_name', 'meal_type', 'meal_period', 'is_active')


class MealCycleBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCycle
        fields = ('id', 'public_id', 'year', 'month', 'cycle_days', 'total_meals')


class MealCyclePlanLineSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    product_role = serializers.CharField(source='ingredient.product_role', read_only=True)

    class Meta:
        model = MealCyclePlanLine
        fields = (
            'id',
            'public_id',
            'plan',
            'ingredient',
            'ingredient_name',
            'product_role',
            'servings_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'public_id',
            'ingredient_name',
            'product_role',
            'created_at',
            'updated_at',
        )

    def validate_servings_count(self, value):
        if value is None or value < 0:
            raise serializers.ValidationError('Servings count must be 0 or greater.')
        return value

    def validate(self, attrs):
        plan = attrs.get('plan') or getattr(self.instance, 'plan', None)
        ingredient = attrs.get('ingredient') or getattr(self.instance, 'ingredient', None)

        if plan is not None and plan.is_finalized:
            raise serializers.ValidationError(
                {'plan': 'Finalized plans cannot be edited. Reopen the plan first.'}
            )
        if ingredient is not None and not ingredient.is_active and self.instance is None:
            raise serializers.ValidationError({'ingredient': 'Ingredient must be active.'})
        if plan and ingredient:
            qs = MealCyclePlanLine.objects.filter(plan=plan, ingredient=ingredient)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'ingredient': 'This ingredient is already on the selected plan.'}
                )
        return attrs


class MealCyclePlanLineBulkItemSerializer(serializers.Serializer):
    ingredient = serializers.PrimaryKeyRelatedField(queryset=Ingredient.objects.all())
    servings_count = serializers.IntegerField(min_value=0)


class MealCyclePlanLineBulkSerializer(serializers.Serializer):
    lines = MealCyclePlanLineBulkItemSerializer(many=True)


class MealCyclePlanSerializer(serializers.ModelSerializer):
    cycle_detail = MealCycleBriefSerializer(source='cycle', read_only=True)
    meal_category_detail = MealCategoryBriefSerializer(source='meal_category', read_only=True)
    lines = MealCyclePlanLineSerializer(many=True, read_only=True)

    class Meta:
        model = MealCyclePlan
        fields = (
            'id',
            'public_id',
            'cycle',
            'cycle_detail',
            'meal_category',
            'meal_category_detail',
            'other_cost_percent',
            'profit_percent',
            'status',
            'snapshot_product_cost',
            'snapshot_other_cost',
            'snapshot_profit',
            'snapshot_total_cost',
            'snapshot_per_meal_rate',
            'finalized_at',
            'notes',
            'lines',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'public_id',
            'cycle_detail',
            'meal_category_detail',
            'status',
            'snapshot_product_cost',
            'snapshot_other_cost',
            'snapshot_profit',
            'snapshot_total_cost',
            'snapshot_per_meal_rate',
            'finalized_at',
            'lines',
            'created_at',
            'updated_at',
        )

    def validate_other_cost_percent(self, value):
        if value is None or value < 0 or value > 100:
            raise serializers.ValidationError('other_cost_percent must be between 0 and 100.')
        return value

    def validate_profit_percent(self, value):
        if value is None or value < 0 or value > 100:
            raise serializers.ValidationError('profit_percent must be between 0 and 100.')
        return value

    def validate(self, attrs):
        cycle = attrs.get('cycle') or getattr(self.instance, 'cycle', None)
        meal_category = attrs.get('meal_category') or getattr(self.instance, 'meal_category', None)
        if self.instance is not None and self.instance.is_finalized:
            editable = set(attrs.keys()) - {'notes'}
            # Allow notes-only patch on finalized; block margin/identity changes
            blocked = editable & {'cycle', 'meal_category', 'other_cost_percent', 'profit_percent'}
            if blocked:
                raise serializers.ValidationError(
                    {'status': 'Finalized plans cannot be edited. Reopen the plan first.'}
                )
        if cycle and meal_category:
            qs = MealCyclePlan.objects.filter(cycle=cycle, meal_category=meal_category)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {'meal_category': 'A plan already exists for this meal package in the selected cycle.'}
                )
        return attrs
