from django.urls import path

from app_config.api.views import AdminAppVersionSettingsView

app_name = 'web_app_config'

urlpatterns = [
    path('version/', AdminAppVersionSettingsView.as_view(), name='version'),
]
