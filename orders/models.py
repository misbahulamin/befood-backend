from django.conf import settings
from django.db import models
from django.db.models import Q


class Cart(models.Model):
    customer = models.ForeignKey('user_management.CustomerProfile', on_delete=models.CASCADE)
    outlet = models.ForeignKey('business.Outlet', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    meal = models.ForeignKey('meals.MealCategory', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    addons = models.JSONField(default=list, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)


class Order(models.Model):
    class OrderStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        ACTIVE = 'active', 'Active'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    customer = models.ForeignKey(
        'user_management.CustomerProfile',
        on_delete=models.CASCADE,
        related_name='meal_orders',
    )
    meal = models.ForeignKey(
        'meals.MealCategory',
        on_delete=models.PROTECT,
        related_name='orders',
    )
    meal_name_snapshot = models.CharField(max_length=255)
    meal_type_snapshot = models.CharField(max_length=20)
    total_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    per_meal_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    order_status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.CONFIRMED,
    )
    order_start_date = models.DateField()
    order_end_date = models.DateField()
    service_days_count = models.PositiveIntegerField()
    order_month = models.CharField(max_length=7)
    customer_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['customer', 'order_month'],
                condition=~Q(order_status='cancelled'),
                name='unique_non_cancelled_order_per_customer_month',
            ),
        ]

    def __str__(self):
        return f'Order #{self.pk} - {self.meal_name_snapshot} ({self.order_month})'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    meal = models.ForeignKey('meals.MealCategory', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    addons = models.JSONField(default=list, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30)
    to_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class OrderReview(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
