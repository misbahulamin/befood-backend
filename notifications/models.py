from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import PublicIdMixin


class NotificationTemplate(models.Model):
    event_type = models.CharField(max_length=100)
    title_template = models.CharField(max_length=255)
    body_template = models.TextField()
    channels = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    notification_type = models.CharField(max_length=50, blank=True, default='')
    screen = models.CharField(max_length=100, blank=True, default='')
    data = models.JSONField(default=dict, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']



class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    push_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=False)


class PushLog(models.Model):
    notification = models.ForeignKey(Notification, on_delete=models.SET_NULL, null=True, blank=True)
    device_token = models.CharField(max_length=255)
    status = models.CharField(max_length=50)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)


class PushCampaign(PublicIdMixin, models.Model):
    class NotificationType(models.TextChoices):
        ORDER = 'order', 'Order'
        WALLET = 'wallet', 'Wallet'
        DELIVERY = 'delivery', 'Delivery'
        PROMOTION = 'promotion', 'Promotion'
        SYSTEM = 'system', 'System'

    class TargetType(models.TextChoices):
        SINGLE_USER = 'single_user', 'Single user'
        SELECTED_USERS = 'selected_users', 'Selected users'
        FILTERED_USERS = 'filtered_users', 'Filtered users'
        ALL_USERS = 'all_users', 'All users'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    title = models.CharField(max_length=255)
    body = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NotificationType.choices)
    data = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='push_campaigns_created',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    idempotency_key = models.CharField(max_length=128, blank=True, db_index=True)
    target_type = models.CharField(max_length=30, choices=TargetType.choices)
    target_config = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING,
        db_index=True,
    )
    total_targets = models.PositiveIntegerField(default=0)
    total_sent = models.PositiveIntegerField(default=0)
    total_failed = models.PositiveIntegerField(default=0)
    total_skipped = models.PositiveIntegerField(default=0)
    error_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='pushcamp_status_created_idx'),
            models.Index(fields=['created_by', 'created_at'], name='pushcamp_creator_created_idx'),
        ]

    def __str__(self):
        return f'{self.title} ({self.status})'


class PushCampaignRecipient(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'

    campaign = models.ForeignKey(
        PushCampaign,
        on_delete=models.CASCADE,
        related_name='recipients',
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    device = models.ForeignKey(
        'user_management.DeviceToken',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    firebase_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['campaign', 'status'], name='pushrecip_campaign_status_idx'),
            models.Index(fields=['user', 'sent_at'], name='pushrecip_user_sent_idx'),
            models.Index(fields=['status', 'campaign'], name='pushrecip_status_campaign_idx'),
        ]

    def __str__(self):
        return f'Campaign {self.campaign_id} → user {self.user_id} ({self.status})'
