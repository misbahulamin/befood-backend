from django.contrib import admin
from .models import Coupon, CouponUsage, Promotion

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)
