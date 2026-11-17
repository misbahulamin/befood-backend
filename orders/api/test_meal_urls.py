from django.urls import path

from orders.api.test_meal_views import (
    TestMealEligibilityView,
    TestMealFunnelEventView,
    TestMealOrderDetailView,
    TestMealOrderListCreateView,
    TestMealPackageListView,
    TestMealQuoteView,
)

app_name = 'test_meals'

urlpatterns = [
    path('eligibility/', TestMealEligibilityView.as_view(), name='eligibility'),
    path('packages/', TestMealPackageListView.as_view(), name='packages'),
    path('quote/', TestMealQuoteView.as_view(), name='quote'),
    path('orders/', TestMealOrderListCreateView.as_view(), name='orders'),
    path('orders/<uuid:public_id>/', TestMealOrderDetailView.as_view(), name='order-detail'),
    path('funnel-events/', TestMealFunnelEventView.as_view(), name='funnel-events'),
]
