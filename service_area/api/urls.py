from django.urls import path

from service_area.api.views import ServiceAreaCheckView, ServiceAreaDemandView

app_name = 'service_area'

urlpatterns = [
    path('check/', ServiceAreaCheckView.as_view(), name='check'),
    path('demand/', ServiceAreaDemandView.as_view(), name='demand'),
]
