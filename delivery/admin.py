from django.contrib import admin
from .models import RiderLocation, DeliveryAssignment, DeliveryTracking, DeliveryFeeRule

@admin.register(RiderLocation)
class RiderLocationAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(DeliveryTracking)
class DeliveryTrackingAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(DeliveryFeeRule)
class DeliveryFeeRuleAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)
