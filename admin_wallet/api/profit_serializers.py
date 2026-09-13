"""Serializers for Admin Profit analytics APIs."""

from rest_framework import serializers

from admin_wallet.models import MealProfitTransaction


class ProfitByPackageRowSerializer(serializers.Serializer):
    package_public_id = serializers.UUIDField()
    package_name = serializers.CharField()
    charged_deliveries = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    food_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)


class ProfitByMealPeriodRowSerializer(serializers.Serializer):
    meal_period = serializers.CharField()
    charged_deliveries = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    food_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit_share_percent = serializers.DecimalField(max_digits=8, decimal_places=2)


class ProfitByCustomerRowSerializer(serializers.Serializer):
    customer_public_id = serializers.UUIDField()
    customer_email = serializers.CharField()
    charged_deliveries = serializers.IntegerField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    food_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)


class DailyProfitChartRowSerializer(serializers.Serializer):
    date = serializers.CharField()
    profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    food_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    charged_deliveries = serializers.IntegerField()


class AdminProfitDashboardSerializer(serializers.Serializer):
    lifetime_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    month_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    today_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    range_start = serializers.CharField()
    range_end = serializers.CharField()
    range_profit = serializers.DecimalField(max_digits=14, decimal_places=2)
    range_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    range_food_cost = serializers.DecimalField(max_digits=14, decimal_places=2)
    range_deliveries = serializers.IntegerField()
    profit_by_package = ProfitByPackageRowSerializer(many=True)
    profit_by_meal_period = ProfitByMealPeriodRowSerializer(many=True)
    profit_by_customer = ProfitByCustomerRowSerializer(many=True)
    daily_profit_chart = DailyProfitChartRowSerializer(many=True)


class MealProfitTransactionSerializer(serializers.ModelSerializer):
    package_public_id = serializers.UUIDField(source='package.public_id', read_only=True)
    package_name = serializers.SerializerMethodField()
    customer_public_id = serializers.UUIDField(source='customer.public_id', read_only=True)
    customer_email = serializers.SerializerMethodField()
    delivery_public_id = serializers.UUIDField(
        source='order_delivery.public_id',
        read_only=True,
    )

    class Meta:
        model = MealProfitTransaction
        fields = (
            'public_id',
            'delivery_public_id',
            'customer_public_id',
            'customer_email',
            'package_public_id',
            'package_name',
            'meal_period',
            'service_date',
            'meal_price',
            'food_cost',
            'operational_cost',
            'profit_amount',
            'profit_percentage',
            'source',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_package_name(self, obj):
        return obj.package_name_snapshot or (obj.package.meal_name if obj.package_id else '')

    def get_customer_email(self, obj):
        if obj.customer_id and obj.customer.user_id:
            return obj.customer.user.email
        return ''
