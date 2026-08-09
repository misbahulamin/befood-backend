from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin
from meals.models import Ingredient, MealCategory
from user_management.models import TimeStampedModel


class SearchDocument(PublicIdMixin, TimeStampedModel):
    """Denormalized customer-discoverable catalog entry."""

    class DocumentType(models.TextChoices):
        PACKAGE = 'package', 'Package'
        INSTANT_MEAL = 'instant_meal', 'Instant Meal'
        FOOD = 'food', 'Food'
        CATEGORY = 'category', 'Category'

    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
        db_index=True,
    )
    title_en = models.CharField(max_length=255)
    title_bn = models.CharField(max_length=255, blank=True, default='')
    short_description = models.TextField(blank=True, default='')
    image_url = models.CharField(max_length=512, blank=True, default='')
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    currency = models.CharField(max_length=3, default='BDT')
    is_active = models.BooleanField(default=True, db_index=True)
    is_available = models.BooleanField(default=True)
    popularity_score = models.PositiveIntegerField(default=0, db_index=True)
    meal_category = models.ForeignKey(
        MealCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_documents',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_documents',
    )
    category_key = models.CharField(max_length=64, blank=True, default='', db_index=True)

    class Meta:
        ordering = ['-popularity_score', 'title_en', 'id']
        indexes = [
            models.Index(fields=['is_active', 'document_type']),
            models.Index(fields=['is_active', '-popularity_score']),
        ]

    def __str__(self):
        return f'{self.document_type}: {self.title_en}'

    @property
    def display_name(self) -> str:
        return self.title_bn or self.title_en


class SearchKeyword(PublicIdMixin, TimeStampedModel):
    """Synonym / Banglish / Bangla / English keyword for a document."""

    class LocaleHint(models.TextChoices):
        BN = 'bn', 'Bangla'
        EN = 'en', 'English'
        BANGLISH = 'banglish', 'Banglish'
        OTHER = 'other', 'Other'

    document = models.ForeignKey(
        SearchDocument,
        on_delete=models.CASCADE,
        related_name='keywords',
    )
    keyword = models.CharField(max_length=255, db_index=True)
    keyword_raw = models.CharField(max_length=255)
    locale_hint = models.CharField(
        max_length=16,
        choices=LocaleHint.choices,
        default=LocaleHint.OTHER,
    )

    class Meta:
        ordering = ['keyword']
        constraints = [
            models.UniqueConstraint(
                fields=['document', 'keyword'],
                name='unique_search_keyword_per_document',
            ),
        ]
        indexes = [
            models.Index(fields=['keyword']),
        ]

    def __str__(self):
        return f'{self.keyword} → {self.document_id}'


class SearchQueryEvent(PublicIdMixin, models.Model):
    """Analytics row for a customer/guest search query."""

    query_original = models.CharField(max_length=255)
    query_normalized = models.CharField(max_length=255, db_index=True)
    result_count = models.PositiveIntegerField(default=0)
    is_zero_result = models.BooleanField(default=False, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_query_events',
    )
    session_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['query_normalized', '-created_at']),
            models.Index(fields=['is_zero_result', '-created_at']),
        ]

    def __str__(self):
        return f'{self.query_normalized} ({self.result_count})'


class SearchClickEvent(PublicIdMixin, models.Model):
    """Analytics row for a result click-through."""

    query_event = models.ForeignKey(
        SearchQueryEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clicks',
    )
    query_original = models.CharField(max_length=255, blank=True, default='')
    query_normalized = models.CharField(max_length=255, blank=True, default='', db_index=True)
    document = models.ForeignKey(
        SearchDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='click_events',
    )
    clicked_type = models.CharField(max_length=32, blank=True, default='')
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='search_click_events',
    )
    session_id = models.CharField(max_length=64, blank=True, default='', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['clicked_type', '-created_at']),
        ]

    def __str__(self):
        return f'click {self.clicked_type} @ {self.position}'


class PopularSearchPin(PublicIdMixin, TimeStampedModel):
    """Optional admin-curated popular search term for empty focus UX."""

    term = models.CharField(max_length=255)
    term_normalized = models.CharField(max_length=255, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['sort_order', 'term']

    def __str__(self):
        return self.term
