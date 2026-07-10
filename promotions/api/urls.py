from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CouponViewSet, CouponUsageViewSet, PromotionViewSet
router = DefaultRouter()
router.register(r'coupon', CouponViewSet)
router.register(r'couponusage', CouponUsageViewSet)
router.register(r'promotion', PromotionViewSet)
urlpatterns = [path("", include(router.urls))]