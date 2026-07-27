from django.contrib import admin

from faqs.models import FaqQuestion, FaqType


class FaqQuestionInline(admin.TabularInline):
    model = FaqQuestion
    extra = 0
    fields = (
        'question',
        'answer',
        'is_published',
        'sort_order',
        'public_id',
    )
    readonly_fields = ('public_id',)
    show_change_link = True


@admin.register(FaqType)
class FaqTypeAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'sort_order',
        'is_active',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('sort_order', 'created_at')
    inlines = [FaqQuestionInline]


@admin.register(FaqQuestion)
class FaqQuestionAdmin(admin.ModelAdmin):
    list_display = (
        'question',
        'type',
        'is_published',
        'sort_order',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_published', 'type')
    search_fields = ('question', 'answer', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('type', 'sort_order', 'created_at')
    autocomplete_fields = ('type',)
