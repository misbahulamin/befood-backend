from django.contrib import admin

from search.models import (
    PopularSearchPin,
    SearchClickEvent,
    SearchDocument,
    SearchKeyword,
    SearchQueryEvent,
)


class SearchKeywordInline(admin.TabularInline):
    model = SearchKeyword
    extra = 1
    readonly_fields = ('public_id', 'keyword')


@admin.register(SearchDocument)
class SearchDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'title_en',
        'title_bn',
        'document_type',
        'is_active',
        'is_available',
        'popularity_score',
        'updated_at',
    )
    list_filter = ('document_type', 'is_active', 'is_available')
    search_fields = ('title_en', 'title_bn', 'public_id', 'category_key', 'short_description')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    raw_id_fields = ('meal_category', 'ingredient')
    inlines = [SearchKeywordInline]


@admin.register(SearchKeyword)
class SearchKeywordAdmin(admin.ModelAdmin):
    list_display = ('keyword_raw', 'keyword', 'locale_hint', 'document', 'created_at')
    list_filter = ('locale_hint',)
    search_fields = ('keyword', 'keyword_raw', 'document__title_en')
    readonly_fields = ('public_id', 'keyword', 'created_at', 'updated_at')
    raw_id_fields = ('document',)


@admin.register(SearchQueryEvent)
class SearchQueryEventAdmin(admin.ModelAdmin):
    list_display = (
        'query_normalized',
        'result_count',
        'is_zero_result',
        'session_id',
        'created_at',
    )
    list_filter = ('is_zero_result',)
    search_fields = ('query_original', 'query_normalized', 'session_id', 'public_id')
    readonly_fields = ('public_id', 'created_at')


@admin.register(SearchClickEvent)
class SearchClickEventAdmin(admin.ModelAdmin):
    list_display = (
        'query_normalized',
        'clicked_type',
        'document',
        'position',
        'created_at',
    )
    list_filter = ('clicked_type',)
    search_fields = ('query_normalized', 'session_id', 'public_id')
    readonly_fields = ('public_id', 'created_at')
    raw_id_fields = ('query_event', 'document', 'user')


@admin.register(PopularSearchPin)
class PopularSearchPinAdmin(admin.ModelAdmin):
    list_display = ('term', 'term_normalized', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('term', 'term_normalized')
    readonly_fields = ('public_id', 'term_normalized', 'created_at', 'updated_at')
