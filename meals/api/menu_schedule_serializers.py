from rest_framework import serializers

from meals.models import (
    MealCyclePlan,
    MenuRevealSettings,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
)
from meals.services.menu_schedule import (
    build_quota_summary,
    create_schedule_for_plan,
    serialize_schedule_assignments,
)


class MonthlyMenuScheduleSerializer(serializers.ModelSerializer):
    plan_id = serializers.PrimaryKeyRelatedField(
        source='plan',
        queryset=MealCyclePlan.objects.all(),
        write_only=True,
        required=True,
    )
    cycle_id = serializers.IntegerField(source='plan.cycle_id', read_only=True)
    meal_category_id = serializers.IntegerField(source='plan.meal_category_id', read_only=True)
    meal_category_name = serializers.CharField(
        source='plan.meal_category.meal_name',
        read_only=True,
    )
    cycle_year = serializers.IntegerField(source='plan.cycle.year', read_only=True)
    cycle_month = serializers.IntegerField(source='plan.cycle.month', read_only=True)
    plan_status = serializers.CharField(source='plan.status', read_only=True)
    assignments = serializers.SerializerMethodField()
    quota_summary = serializers.SerializerMethodField()

    class Meta:
        model = MonthlyMenuSchedule
        fields = (
            'id',
            'plan_id',
            'plan',
            'cycle_id',
            'cycle_year',
            'cycle_month',
            'meal_category_id',
            'meal_category_name',
            'plan_status',
            'status',
            'notes',
            'published_at',
            'assignments',
            'quota_summary',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'plan',
            'status',
            'published_at',
            'created_at',
            'updated_at',
            'assignments',
            'quota_summary',
        )

    def get_assignments(self, obj):
        return serialize_schedule_assignments(obj)

    def get_quota_summary(self, obj):
        return build_quota_summary(obj)

    def create(self, validated_data):
        plan = validated_data['plan']
        notes = validated_data.get('notes', '')
        return create_schedule_for_plan(plan, notes=notes)


class MonthlyMenuScheduleUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MonthlyMenuSchedule
        fields = ('notes',)


class MenuAssignmentSlotSerializer(serializers.Serializer):
    service_date = serializers.DateField()
    meal_period = serializers.ChoiceField(choices=MonthlyMenuSlot.MealPeriod.choices)
    ingredient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=True,
    )


class MenuAssignmentBulkSerializer(serializers.Serializer):
    assignments = MenuAssignmentSlotSerializer(many=True)


class MenuSyncRequestSerializer(serializers.Serializer):
    source_schedule_id = serializers.IntegerField(min_value=1)


class MenuSyncApplySerializer(serializers.Serializer):
    source_schedule_id = serializers.IntegerField(min_value=1, required=False)
    assignments = MenuAssignmentSlotSerializer(many=True, required=False)

    def validate(self, attrs):
        if not attrs.get('source_schedule_id') and attrs.get('assignments') is None:
            raise serializers.ValidationError(
                'Provide source_schedule_id and/or assignments.'
            )
        return attrs


class MenuRevealSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuRevealSettings
        fields = (
            'timezone',
            'lunch_reveal_time',
            'dinner_reveal_time',
            'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(f'Unknown timezone: {value}') from exc
        return value
