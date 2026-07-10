from django.contrib import admin

from .models import Cart, CartItem, Order, OrderItem, OrderReview, OrderStatusHistory


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
        'order_status',
        'order_start_date',
        'order_end_date',
        'order_month',
        'total_price_snapshot',
        'created_at',
    )
    list_filter = ('order_status', 'meal_type_snapshot', 'order_month', 'created_at')
    search_fields = ('customer__user__email', 'meal_name_snapshot', 'order_month')
    readonly_fields = (
        'meal_name_snapshot',
        'meal_type_snapshot',
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
