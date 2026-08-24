from django.contrib import admin

from .models import (
    Cart,
    CartItem,
    CustomerSubscription,
    MealDemandSnapshot,
    MealOffSettings,
    Order,
    OrderDelivery,
    OrderItem,
    OrderReview,
    OrderStatusHistory,
    OrderWalletSettings,
)


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'outlet', 'created_at')
    search_fields = ('customer__user__email',)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'cart', 'meal', 'quantity', 'unit_price')
    search_fields = ('cart__id', 'meal__meal_name')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'meal_name_snapshot',
        'meal_type_snapshot',
        'meal_period_snapshot',
        'order_status',
        'order_start_date',
        'order_end_date',
        'order_month',
        'total_price_snapshot',
        'created_at',
    )
    list_filter = (
        'order_status',
        'meal_type_snapshot',
        'meal_period_snapshot',
        'order_month',
        'created_at',
    )
    search_fields = ('customer__user__email', 'meal_name_snapshot', 'order_month')
    readonly_fields = (
        'meal_name_snapshot',
        'meal_type_snapshot',
        'meal_period_snapshot',
        'total_price_snapshot',
        'per_meal_price_snapshot',
        'order_start_date',
        'order_end_date',
        'service_days_count',
        'order_month',
        'created_at',
        'updated_at',
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'meal', 'quantity', 'line_total')
    search_fields = ('order__id', 'meal__meal_name')


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'from_status', 'to_status', 'changed_by', 'created_at')
    search_fields = ('order__id', 'from_status', 'to_status')
    readonly_fields = ('created_at',)


@admin.register(OrderReview)
class OrderReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'rating', 'created_at')
    search_fields = ('order__id',)


@admin.register(CustomerSubscription)
class CustomerSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'public_id',
        'customer',
        'meal_name_snapshot',
        'meal_period_snapshot',
        'status',
        'started_on',
        'cancel_effective_on',
        'cancelled_at',
        'created_at',
    )
    list_filter = ('status', 'meal_period_snapshot', 'started_on', 'created_at')
    search_fields = (
        'public_id',
        'customer__user__email',
        'meal_name_snapshot',
    )
    readonly_fields = (
        'public_id',
        'meal_name_snapshot',
        'meal_period_snapshot',
        'created_at',
        'updated_at',
    )
    raw_id_fields = ('customer', 'meal')
    date_hierarchy = 'started_on'


@admin.register(OrderDelivery)
class OrderDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'subscription',
        'service_date',
        'meal_period',
        'status',
        'payment_status',
        'charged_amount',
        'skip_source',
        'delivery_label_snapshot',
        'delivery_area_snapshot',
        'marked_by',
        'marked_at',
        'created_at',
    )
    list_filter = (
        'status',
        'payment_status',
        'skip_source',
        'meal_period',
        'service_date',
        'created_at',
    )
    search_fields = (
        'order__id',
        'order__customer__user__email',
        'subscription__public_id',
        'subscription__customer__user__email',
        'note',
        'delivery_full_address_snapshot',
        'delivery_label_snapshot',
    )
    readonly_fields = (
        'public_id',
        'created_at',
        'updated_at',
        'marked_at',
        'payment_status',
        'charged_amount',
        'wallet_transaction',
        'delivery_label_snapshot',
        'delivery_full_address_snapshot',
        'delivery_area_snapshot',
        'delivery_city_snapshot',
        'delivery_latitude_snapshot',
        'delivery_longitude_snapshot',
    )
    date_hierarchy = 'service_date'
    autocomplete_fields = ('delivery_place',)
    raw_id_fields = ('wallet_transaction', 'order', 'subscription')


@admin.register(MealOffSettings)
class MealOffSettingsAdmin(admin.ModelAdmin):
    list_display = ('timezone', 'lunch_off_time', 'dinner_off_time', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(OrderWalletSettings)
class OrderWalletSettingsAdmin(admin.ModelAdmin):
    list_display = ('min_wallet_balance_to_order', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(MealDemandSnapshot)
class MealDemandSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        'service_date',
        'meal_period',
        'package',
        'expected_meal_count',
        'meal_off_count',
        'final_cooking_count',
        'confirmation_status',
        'captured_at',
        'confirmed_at',
    )
    list_filter = ('meal_period', 'confirmation_status', 'service_date')
    search_fields = ('package__meal_name',)
    readonly_fields = (
        'service_date',
        'meal_period',
        'package',
        'expected_meal_count',
        'meal_off_count',
        'final_cooking_count',
        'total_customers',
        'confirmation_status',
        'ingredient_requirements',
        'captured_at',
        'confirmed_at',
        'created_at',
        'updated_at',
    )
    date_hierarchy = 'service_date'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
