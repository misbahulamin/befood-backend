from django.urls import path

from orders.api.guest_meal_views import (
    GuestMealDetailView,
    GuestMealListCreateView,
    GuestMealPreviewView,
    GuestMealUsageView,
)

app_name = 'guest_meals'

urlpatterns = [
    path('usage/', GuestMealUsageView.as_view(), name='usage'),
    path('preview/', GuestMealPreviewView.as_view(), name='preview'),
    path('', GuestMealListCreateView.as_view(), name='list-create'),
    path('<uuid:public_id>/', GuestMealDetailView.as_view(), name='detail'),
]
