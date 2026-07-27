from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BlogArticleViewSet, BlogCategoryViewSet, PublicBlogArticleViewSet

app_name = 'blogs'

router = DefaultRouter()
# Register named prefixes first so they are never treated as a public_id.
# "public/popular" is a list @action on PublicBlogArticleViewSet (not a public_id).
router.register('public', PublicBlogArticleViewSet, basename='public')
router.register('categories', BlogCategoryViewSet, basename='categories')
router.register('articles', BlogArticleViewSet, basename='articles')

urlpatterns = [
    path('', include(router.urls)),
]
