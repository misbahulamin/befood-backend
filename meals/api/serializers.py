from decimal import Decimal

from rest_framework import serializers

from meals.models import MealCategory
from meals.services.meal_image import validate_image_extension, validate_image_size
from meals.services.pricing import calculate_per_meal_price


class MealListSerializer(serializers.ModelSerializer):
    meal_thumbnail = serializers.SerializerMethodField()
    meal_type_display = serializers.CharField(source='get_meal_type_display', read_only=True)
    per_meal_price = serializers.SerializerMethodField()

    class Meta:
        model = MealCategory
        fields = (
            'id',
            'meal_name',
            'total_price',
            'per_meal_price',
            'meal_thumbnail',
            'meal_type',
            'meal_type_display',
            'is_active',
            'created_at',
            'updated_at',
        )

    def get_per_meal_price(self, obj):
        return str(calculate_per_meal_price(obj.total_price))

    def get_meal_thumbnail(self, obj):
        if not obj.meal_thumbnail:
            return None
        request = self.context.get('request')
        url = obj.meal_thumbnail.url
        return request.build_absolute_uri(url) if request else url


class MealDetailSerializer(MealListSerializer):
    class Meta(MealListSerializer.Meta):
        fields = MealListSerializer.Meta.fields + ('description',)


class MealCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealCategory
        fields = (
            'meal_name',
            'total_price',
            'meal_thumbnail',
            'meal_type',
            'description',
            'is_active',
        )

    def validate_total_price(self, value):
        if value is None or value <= Decimal('0'):
            raise serializers.ValidationError('Total price must be greater than 0.')
        return value

    def validate_meal_type(self, value):
        valid_values = {choice.value for choice in MealCategory.MealType}
        if value not in valid_values:
            raise serializers.ValidationError(
                f'Invalid meal type. Allowed values: {", ".join(sorted(valid_values))}.'
            )
        return value

    def validate_meal_thumbnail(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, attrs):
        thumbnail = attrs.get('meal_thumbnail')
        if self.instance is None and not thumbnail:
            raise serializers.ValidationError({'meal_thumbnail': 'Meal thumbnail is required.'})
        return attrs
