from django.urls import path

from referrals.api.views import (
    AdminReferralAnalyticsView,
    AdminReferralCommissionsExportView,
    AdminReferralCommissionsView,
    AdminReferralCustomerDetailView,
    AdminReferralManualAdjustView,
    AdminReferralProgramSettingsView,
    AdminReferralRelationshipsView,
    AdminReferralReverseView,
)

urlpatterns = [
    path(
        'settings/',
        AdminReferralProgramSettingsView.as_view(),
        name='admin-referral-program-settings',
    ),
    path('analytics/', AdminReferralAnalyticsView.as_view(), name='admin-referral-analytics'),
    path(
        'relationships/',
        AdminReferralRelationshipsView.as_view(),
        name='admin-referral-relationships',
    ),
    path(
        'commissions/',
        AdminReferralCommissionsView.as_view(),
        name='admin-referral-commissions',
    ),
    path(
        'commissions/export/',
        AdminReferralCommissionsExportView.as_view(),
        name='admin-referral-commissions-export',
    ),
    path(
        'commissions/<uuid:public_id>/reverse/',
        AdminReferralReverseView.as_view(),
        name='admin-referral-commission-reverse',
    ),
    path(
        'adjustments/',
        AdminReferralManualAdjustView.as_view(),
        name='admin-referral-manual-adjust',
    ),
    path(
        'customers/<uuid:public_id>/',
        AdminReferralCustomerDetailView.as_view(),
        name='admin-referral-customer-detail',
    ),
]
