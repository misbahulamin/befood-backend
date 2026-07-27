from django.contrib import admin

from blogs.models import BlogArticle, BlogCategory


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'slug',
        'sort_order',
        'is_active',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'public_id')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    ordering = ('sort_order', 'created_at')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(BlogArticle)
class BlogArticleAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'category',
        'author',
        'is_published',
        'published_at',
        'view_count',
        'public_id',
        'updated_at',
    )
    list_filter = ('is_published', 'category')
    search_fields = ('title', 'excerpt', 'slug', 'public_id')
    readonly_fields = (
        'public_id',
        'author',
        'view_count',
        'published_at',
        'created_at',
        'updated_at',
    )
    ordering = ('-published_at', '-created_at')
    autocomplete_fields = ('category',)
    raw_id_fields = ('author',)
    prepopulated_fields = {'slug': ('title',)}
