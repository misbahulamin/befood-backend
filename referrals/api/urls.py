from django.urls import path

from referrals.api.views import (
    ReferralMeView,
    ReferralMyCommissionsView,
    ReferralReferredUsersView,
    ReferralShareView,
    ReferralValidateView,
)

urlpatterns = [
    path('me/', ReferralMeView.as_view(), name='referral-me'),
    path('me/share/', ReferralShareView.as_view(), name='referral-share'),
    path('me/referred-users/', ReferralReferredUsersView.as_view(), name='referral-referred-users'),
    path('me/commissions/', ReferralMyCommissionsView.as_view(), name='referral-my-commissions'),
    path('validate/', ReferralValidateView.as_view(), name='referral-validate'),
]
