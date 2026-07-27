import django_filters
from django.db.models import Q

from blogs.models import BlogArticle, BlogCategory


class BlogCategoryFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = BlogCategory
        fields = ['is_active', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(slug__icontains=value)
        )


class BlogArticleFilter(django_filters.FilterSet):
    is_published = django_filters.BooleanFilter()
    category_public_id = django_filters.UUIDFilter(field_name='category__public_id')
    search = django_filters.CharFilter(method='filter_search')

    class Meta:
        model = BlogArticle
        fields = ['is_published', 'category_public_id', 'search']

    def filter_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(excerpt__icontains=value)
        )


class PublicBlogArticleFilter(django_filters.FilterSet):
    category = django_filters.UUIDFilter(field_name='category__public_id')
    q = django_filters.CharFilter(method='filter_q')

    class Meta:
        model = BlogArticle
        fields = ['category', 'q']

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) | Q(excerpt__icontains=value)
        )
