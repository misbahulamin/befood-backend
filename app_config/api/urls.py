from django.urls import path

from app_config.api.views import PublicAppVersionView

app_name = 'app_config'

urlpatterns = [
    path('version/', PublicAppVersionView.as_view(), name='version'),
]
