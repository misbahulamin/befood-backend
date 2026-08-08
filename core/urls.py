from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('user_management/', include('user_management.api.urls')),
    path('meals/', include('meals.api.urls')),
    path('orders/', include('orders.api.urls')),
    path('api/v1/web/orders/', include('orders.api.web_urls')),
    path('api/v1/web/customers/', include('user_management.api.web_urls')),
    path('notices/', include('notices.api.urls')),
    path('announcements/', include('announcements.api.urls')),
    path('assets/', include('assets.api.urls')),
    path('wallet/', include('wallet.api.urls')),
    path('faqs/', include('faqs.api.urls')),
    path('blogs/', include('blogs.api.urls')),
    path('onahar/', include('onahar.api.urls')),
    path('api/v1/web/onahar/', include('onahar.api.web_urls')),
    path('api/v1/web/admin-wallet/', include('admin_wallet.api.web_urls')),
    path('api/v1/web/inventory/', include('inventory.api.web_urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
