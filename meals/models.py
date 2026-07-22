from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from meals.services.meal_image import meal_thumbnail_upload_path
from meals.services.pricing import get_month_days, total_meals_for_month


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
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Published package price from cycle finalize. Null until first finalize.',
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

    @property
    def pricing_status(self) -> str:
        return 'priced' if self.total_price is not None else 'unpriced'


class Ingredient(models.Model):
    class ProductRole(models.TextChoices):
        MAIN = 'main', 'Main'
        SIDE = 'side', 'Side'
        STAPLE = 'staple', 'Staple'
        SEASONING = 'seasoning', 'Seasoning'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=255, unique=True)
    price_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    customers_per_kg = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    cost_per_customer = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.000001'))],
        help_text='Required for flat-cost items. Ignored when kg pricing is complete.',
    )
    pieces_per_kg = models.PositiveIntegerField(null=True, blank=True)
    product_role = models.CharField(
        max_length=20,
        choices=ProductRole.choices,
        default=ProductRole.OTHER,
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def has_kg_pricing(self) -> bool:
        return self.price_per_kg is not None and self.customers_per_kg is not None

    def clean(self):
        super().clean()
        has_price = self.price_per_kg is not None
        has_customers = self.customers_per_kg is not None
        if has_price != has_customers:
            raise ValidationError(
                {
                    'price_per_kg': 'Provide both price_per_kg and customers_per_kg, or neither.',
                    'customers_per_kg': 'Provide both price_per_kg and customers_per_kg, or neither.',
                }
            )
        if not self.has_kg_pricing and self.cost_per_customer is None:
            raise ValidationError(
                {
                    'cost_per_customer': (
                        'Provide kg pricing (price_per_kg and customers_per_kg) '
                        'or a flat cost_per_customer.'
                    )
                }
            )
        if self.pieces_per_kg is not None and self.pieces_per_kg <= 0:
            raise ValidationError({'pieces_per_kg': 'Pieces per kg must be greater than 0 when provided.'})


class MealCycle(models.Model):
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    cycle_days = models.PositiveSmallIntegerField()
    total_meals = models.PositiveIntegerField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month']
        constraints = [
            models.UniqueConstraint(fields=['year', 'month'], name='unique_meal_cycle_year_month'),
        ]

    def __str__(self):
        return f'{self.year}-{self.month:02d} ({self.total_meals} meals)'

    def save(self, *args, **kwargs):
        self.cycle_days = get_month_days(self.year, self.month)
        self.total_meals = total_meals_for_month(self.year, self.month)
        super().save(*args, **kwargs)


class MealCyclePlan(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        FINALIZED = 'finalized', 'Finalized'

    cycle = models.ForeignKey(
        MealCycle,
        on_delete=models.CASCADE,
        related_name='plans',
    )
    meal_category = models.ForeignKey(
        MealCategory,
        on_delete=models.CASCADE,
        related_name='cycle_plans',
    )
    other_cost_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    profit_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    snapshot_product_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    snapshot_other_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    snapshot_profit = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    snapshot_total_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    snapshot_per_meal_rate = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'meal_category'],
                name='unique_meal_cycle_plan_per_category',
            ),
        ]

    def __str__(self):
        return f'{self.cycle} / {self.meal_category.meal_name} ({self.status})'

    @property
    def is_finalized(self) -> bool:
        return self.status == self.Status.FINALIZED


class MealCyclePlanLine(models.Model):
    plan = models.ForeignKey(
        MealCyclePlan,
        on_delete=models.CASCADE,
        related_name='lines',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name='cycle_plan_lines',
    )
    servings_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['ingredient__name']
        constraints = [
            models.UniqueConstraint(
                fields=['plan', 'ingredient'],
                name='unique_cycle_plan_line_ingredient',
            ),
        ]

    def __str__(self):
        return f'{self.plan_id}: {self.ingredient.name} × {self.servings_count}'
