from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AdminSliderViewSet, PublicSliderViewSet

app_name = 'sliders'

admin_router = DefaultRouter()
admin_router.register('', AdminSliderViewSet, basename='admin-sliders')

public_router = DefaultRouter()
public_router.register('', PublicSliderViewSet, basename='sliders')

urlpatterns = [
    path('admin/', include((admin_router.urls, 'admin-sliders'))),
    path('', include((public_router.urls, 'public-sliders'))),
]
