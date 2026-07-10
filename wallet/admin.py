from django.contrib import admin
from .models import Wallet, WalletTransaction, TopUpRequest, WalletPayment

@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(TopUpRequest)
class TopUpRequestAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)

@admin.register(WalletPayment)
class WalletPaymentAdmin(admin.ModelAdmin):
    list_display = ("id",)
    search_fields = ("id",)
