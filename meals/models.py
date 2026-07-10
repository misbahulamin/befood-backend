from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from meals.services.meal_image import meal_thumbnail_upload_path


class MealCategory(models.Model):
    class MealType(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        HALF_MONTHLY = 'half_monthly', 'Half Monthly'
        MONTHLY = 'monthly', 'Monthly'
        SIX_MONTHS = 'six_months', 'Six Months'
        YEARLY = 'yearly', 'Yearly'

    meal_name = models.CharField(max_length=255)
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    meal_thumbnail = models.ImageField(upload_to=meal_thumbnail_upload_path)
    meal_type = models.CharField(max_length=20, choices=MealType.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Meal Category'
        verbose_name_plural = 'Meal Categories'

    def __str__(self):
        return self.meal_name
