from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import PublicIdMixin


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


class Order(PublicIdMixin, models.Model):
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
    meal_period_snapshot = models.CharField(
        max_length=10,
        help_text='lunch | dinner | both at purchase time.',
    )
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


class OrderDelivery(PublicIdMixin, models.Model):
    class MealPeriod(models.TextChoices):
        LUNCH = 'lunch', 'Lunch'
        DINNER = 'dinner', 'Dinner'

    class DeliveryStatus(models.TextChoices):
        SCHEDULED = 'scheduled', 'Scheduled'
        DELIVERED = 'delivered', 'Delivered'
        SKIPPED = 'skipped', 'Skipped'
        MISSED = 'missed', 'Missed'

    class SkipSource(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='deliveries')
    service_date = models.DateField()
    meal_period = models.CharField(max_length=20, choices=MealPeriod.choices)
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.SCHEDULED,
    )
    skip_source = models.CharField(
        max_length=20,
        choices=SkipSource.choices,
        null=True,
        blank=True,
        help_text='Who initiated a skip: customer meal-off or admin mark.',
    )
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='marked_order_deliveries',
    )
    marked_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['service_date', 'meal_period', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['order', 'service_date', 'meal_period'],
                name='unique_order_delivery_slot',
            ),
        ]
        indexes = [
            models.Index(fields=['service_date', 'status']),
            models.Index(fields=['order', 'status']),
        ]

    def __str__(self):
        return f'Delivery #{self.pk} order={self.order_id} {self.service_date} {self.meal_period}'


class MealOffSettings(models.Model):
    """Singleton: customer meal-off cutoffs for lunch (previous day) and dinner (same day)."""

    timezone = models.CharField(max_length=64, default='Asia/Dhaka')
    lunch_off_time = models.TimeField(
        default=time(23, 59),
        help_text='Deadline time on the calendar day before the lunch service date.',
    )
    dinner_off_time = models.TimeField(
        default=time(14, 0),
        help_text='Deadline time on the dinner service date.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Meal off settings'
        verbose_name_plural = 'Meal off settings'

    def __str__(self):
        return (
            f'Meal-off lunch={self.lunch_off_time} dinner={self.dinner_off_time} '
            f'({self.timezone})'
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls) -> 'MealOffSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
