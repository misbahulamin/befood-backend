from django.contrib import admin
from .models import PaymentMethod, PaymentIntent, PaymentTransaction, PaymentWebhookLog, Refund

@admin.register(PaymentMethod)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(PaymentIntent)
class PaymentIntentAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(PaymentWebhookLog)
class PaymentWebhookLogAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)
