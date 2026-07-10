from django.contrib import admin
from .models import NotificationTemplate, Notification, NotificationPreference, PushLog

@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(PushLog)
class PushLogAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)
