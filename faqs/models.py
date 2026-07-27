from django.core.exceptions import ValidationError
from django.db import models

from core.models import PublicIdMixin


class FaqType(PublicIdMixin, models.Model):
    """Category/section for FAQ questions on the public FAQ page."""

    name = models.CharField(max_length=150, unique=True)
    sort_order = models.IntegerField(
        default=0,
        help_text='Lower values appear first on the FAQ page.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at', 'id']
        verbose_name = 'FAQ type'
        verbose_name_plural = 'FAQ types'
        indexes = [
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        name = (self.name or '').strip()
        if not name:
            errors['name'] = 'Name is required.'
        else:
            self.name = name
        if errors:
            raise ValidationError(errors)


class FaqQuestion(PublicIdMixin, models.Model):
    """Question and answer belonging to exactly one FAQ type."""

    type = models.ForeignKey(
        FaqType,
        on_delete=models.PROTECT,
        related_name='questions',
    )
    question = models.CharField(max_length=500)
    answer = models.TextField()
    is_published = models.BooleanField(default=False)
    sort_order = models.IntegerField(
        default=0,
        help_text='Lower values appear first within the type.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at', 'id']
        verbose_name = 'FAQ question'
        verbose_name_plural = 'FAQ questions'
        indexes = [
            models.Index(fields=['is_published', 'sort_order']),
            models.Index(fields=['type', 'is_published', 'sort_order']),
        ]

    def __str__(self):
        return self.question[:80]

    def clean(self):
        errors = {}
        question = (self.question or '').strip()
        answer = (self.answer or '').strip()
        if not question:
            errors['question'] = 'Question is required.'
        else:
            self.question = question
        if not answer:
            errors['answer'] = 'Answer is required.'
        else:
            self.answer = answer
        if errors:
            raise ValidationError(errors)
