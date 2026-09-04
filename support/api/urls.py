from django.urls import path

from support.api.views import CustomerInboxView, CustomerMessageCreateView

app_name = 'support'

urlpatterns = [
    path('inbox/', CustomerInboxView.as_view(), name='customer-inbox'),
    path('messages/', CustomerMessageCreateView.as_view(), name='customer-messages'),
]
