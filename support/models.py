from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import PublicIdMixin


class SupportConversation(PublicIdMixin, models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'
        ARCHIVED = 'archived', 'Archived'

    customer = models.OneToOneField(
        'user_management.CustomerProfile',
        on_delete=models.CASCADE,
        related_name='support_conversation',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    last_message = models.CharField(max_length=255, blank=True, default='')
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    customer_unread_count = models.PositiveIntegerField(default=0)
    admin_unread_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-last_message_at', '-id']
        indexes = [
            models.Index(fields=['-last_message_at', '-id']),
            models.Index(fields=['status', '-last_message_at']),
        ]

    def __str__(self):
        return f'SupportConversation({self.public_id}) customer={self.customer_id}'


class SupportMessage(PublicIdMixin, models.Model):
    class SenderType(models.TextChoices):
        CUSTOMER = 'customer', 'Customer'
        ADMIN = 'admin', 'Admin'
        SYSTEM = 'system', 'System'

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender_type = models.CharField(max_length=20, choices=SenderType.choices, db_index=True)
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='support_messages',
    )
    body = models.TextField()
    is_read_by_customer = models.BooleanField(default=False)
    is_read_by_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['created_at', 'id']
        indexes = [
            models.Index(fields=['conversation', 'created_at', 'id']),
            models.Index(fields=['conversation', 'is_read_by_admin']),
            models.Index(fields=['conversation', 'is_read_by_customer']),
        ]

    def __str__(self):
        return f'SupportMessage({self.public_id}) {self.sender_type}'
