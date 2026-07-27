from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FaqQuestionViewSet, FaqTypeViewSet, PublicFaqCatalogViewSet

app_name = 'faqs'

router = DefaultRouter()
# Register named prefixes first so they are never treated as a public_id.
router.register('public', PublicFaqCatalogViewSet, basename='public')
router.register('types', FaqTypeViewSet, basename='types')
router.register('questions', FaqQuestionViewSet, basename='questions')

urlpatterns = [
    path('', include(router.urls)),
]
