from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AssetCategoryViewSet, PermanentAssetViewSet

app_name = 'assets'

router = DefaultRouter()
# Register categories first so "categories" is not treated as an asset public_id.
router.register('categories', AssetCategoryViewSet, basename='categories')
router.register('', PermanentAssetViewSet, basename='assets')

urlpatterns = [
    path('', include(router.urls)),
]
