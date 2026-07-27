from django.contrib import admin

from assets.models import AssetCategory, PermanentAsset


@admin.register(AssetCategory)
class AssetCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'public_id', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('name',)


@admin.register(PermanentAsset)
class PermanentAssetAdmin(admin.ModelAdmin):
    list_display = (
        'asset_tag',
        'name',
        'category',
        'status',
        'quantity',
        'outlet',
        'is_active',
        'public_id',
        'updated_at',
    )
    list_filter = ('status', 'is_active', 'category')
    search_fields = (
        'name',
        'asset_tag',
        'serial_number',
        'brand',
        'model',
        'public_id',
    )
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    raw_id_fields = ('outlet',)
    ordering = ('name', 'asset_tag')
