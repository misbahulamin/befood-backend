from django.urls import path

from wallet.api.delivery_fee_views import (
    DeliveryFeeLifetimeReportView,
    DeliveryFeeMonthlyReportView,
    DeliveryFeePaymentListView,
)

app_name = 'web_delivery_fees'

urlpatterns = [
    path('payments/', DeliveryFeePaymentListView.as_view(), name='payment-list'),
    path(
        'reports/monthly/',
        DeliveryFeeMonthlyReportView.as_view(),
        name='report-monthly',
    ),
    path(
        'reports/lifetime/',
        DeliveryFeeLifetimeReportView.as_view(),
        name='report-lifetime',
    ),
]
