from django.contrib import admin

from .models import (
    Ingredient,
    InstantMealSettings,
    MealCategory,
    MealCycle,
    MealCyclePlan,
    MealCyclePlanLine,
    MenuRevealSettings,
    MonthlyMenuSchedule,
    MonthlyMenuSlot,
    MonthlyMenuSlotItem,
    OperationalCostItem,
    OperationalCostMonth,
)


class MealCyclePlanLineInline(admin.TabularInline):
    model = MealCyclePlanLine
    extra = 0
    autocomplete_fields = ('ingredient',)


class OperationalCostItemInline(admin.TabularInline):
    model = OperationalCostItem
    extra = 0


class MonthlyMenuSlotItemInline(admin.TabularInline):
    model = MonthlyMenuSlotItem
    extra = 0
    autocomplete_fields = ('ingredient',)


class MonthlyMenuSlotInline(admin.TabularInline):
    model = MonthlyMenuSlot
    extra = 0
    show_change_link = True


@admin.register(MealCategory)
class MealCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'meal_name',
        'public_id',
        'total_price',
        'meal_type',
        'meal_period',
        'is_active',
        'is_subscribable',
        'created_at',
    )
    search_fields = ('meal_name', 'public_id')
    list_filter = ('meal_type', 'meal_period', 'is_active', 'is_subscribable')
    readonly_fields = ('public_id', 'created_at', 'updated_at')


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'price_per_kg',
        'customers_per_kg',
        'cost_per_customer',
        'pieces_per_kg',
        'is_active',
        'is_customer_visible',
        'created_at',
    )
    search_fields = ('name',)
    list_filter = ('is_active', 'is_customer_visible')
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
    list_display = ('plan', 'ingredient', 'product_role', 'servings_count', 'updated_at')
    list_filter = ('plan__status', 'product_role')
    search_fields = ('ingredient__name', 'plan__meal_category__meal_name')
    autocomplete_fields = ('plan', 'ingredient')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(OperationalCostMonth)
class OperationalCostMonthAdmin(admin.ModelAdmin):
    list_display = ('year', 'month', 'target_meal_quantity', 'created_at')
    list_filter = ('year', 'month')
    search_fields = ('year', 'month', 'notes')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    inlines = [OperationalCostItemInline]


@admin.register(OperationalCostItem)
class OperationalCostItemAdmin(admin.ModelAdmin):
    list_display = ('month', 'name', 'amount', 'sort_order', 'updated_at')
    list_filter = ('month__year', 'month__month')
    search_fields = ('name',)
    autocomplete_fields = ('month',)
    readonly_fields = ('public_id', 'created_at', 'updated_at')


@admin.register(MonthlyMenuSchedule)
class MonthlyMenuScheduleAdmin(admin.ModelAdmin):
    list_display = ('plan', 'status', 'published_at', 'created_at')
    list_filter = ('status', 'plan__cycle__year', 'plan__cycle__month')
    search_fields = ('plan__meal_category__meal_name',)
    autocomplete_fields = ('plan',)
    readonly_fields = ('published_at', 'created_at', 'updated_at')
    inlines = [MonthlyMenuSlotInline]


@admin.register(MonthlyMenuSlot)
class MonthlyMenuSlotAdmin(admin.ModelAdmin):
    list_display = ('schedule', 'service_date', 'meal_period')
    list_filter = ('meal_period',)
    search_fields = ('schedule__plan__meal_category__meal_name',)
    autocomplete_fields = ('schedule',)
    inlines = [MonthlyMenuSlotItemInline]


@admin.register(MonthlyMenuSlotItem)
class MonthlyMenuSlotItemAdmin(admin.ModelAdmin):
    list_display = ('slot', 'ingredient', 'created_at')
    autocomplete_fields = ('slot', 'ingredient')


@admin.register(MenuRevealSettings)
class MenuRevealSettingsAdmin(admin.ModelAdmin):
    list_display = ('timezone', 'lunch_reveal_time', 'dinner_reveal_time', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(InstantMealSettings)
class InstantMealSettingsAdmin(admin.ModelAdmin):
    list_display = ('profit_percent', 'duration_days', 'updated_at')
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        return not InstantMealSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
