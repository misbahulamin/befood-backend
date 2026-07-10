from django.conf import settings
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

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
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

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
