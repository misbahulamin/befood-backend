from django.contrib import admin

from .models import Ingredient, MealCategory, MealCycle, MealCyclePlan, MealCyclePlanLine


class MealCyclePlanLineInline(admin.TabularInline):
    model = MealCyclePlanLine
    extra = 0
    autocomplete_fields = ('ingredient',)


@admin.register(MealCategory)
class MealCategoryAdmin(admin.ModelAdmin):
    list_display = ('meal_name', 'total_price', 'meal_type', 'is_active', 'created_at')
    search_fields = ('meal_name',)
    list_filter = ('meal_type', 'is_active')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'product_role',
        'price_per_kg',
        'customers_per_kg',
        'cost_per_customer',
        'pieces_per_kg',
        'is_active',
        'created_at',
    )
    search_fields = ('name',)
    list_filter = ('is_active', 'product_role')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MealCycle)
class MealCycleAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'cycle_days', 'total_meals', 'created_at')
    list_filter = ('year', 'month')
    search_fields = ('year', 'month')
    readonly_fields = ('cycle_days', 'total_meals', 'created_at', 'updated_at')


@admin.register(MealCyclePlan)
class MealCyclePlanAdmin(admin.ModelAdmin):
    list_display = (
        'cycle',
        'meal_category',
        'status',
        'other_cost_percent',
        'profit_percent',
        'snapshot_per_meal_rate',
        'finalized_at',
    )
    list_filter = ('status', 'cycle__year', 'cycle__month')
    search_fields = ('meal_category__meal_name',)
    autocomplete_fields = ('cycle', 'meal_category')
    readonly_fields = (
        'snapshot_product_cost',
        'snapshot_other_cost',
        'snapshot_profit',
        'snapshot_total_cost',
        'snapshot_per_meal_rate',
        'finalized_at',
        'created_at',
        'updated_at',
    )
    inlines = [MealCyclePlanLineInline]


@admin.register(MealCyclePlanLine)
class MealCyclePlanLineAdmin(admin.ModelAdmin):
    list_display = ('plan', 'ingredient', 'servings_count', 'updated_at')
    list_filter = ('plan__status', 'ingredient__product_role')
    search_fields = ('ingredient__name', 'plan__meal_category__meal_name')
    autocomplete_fields = ('plan', 'ingredient')
    readonly_fields = ('created_at', 'updated_at')
