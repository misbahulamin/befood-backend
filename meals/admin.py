from django.contrib import admin

from .models import MealCategory


@admin.register(MealCategory)
class MealCategoryAdmin(admin.ModelAdmin):
    list_display = ('meal_name', 'total_price', 'meal_type', 'is_active', 'created_at')
    search_fields = ('meal_name',)
    list_filter = ('meal_type', 'is_active')
    readonly_fields = ('created_at', 'updated_at')
