from django.urls import path

from onahar.api.views import (
    OnaharLeaderboardView,
    OnaharMeHistoryView,
    OnaharMePrivacyView,
    OnaharMeView,
    OnaharPublicDistributionDetailView,
    OnaharPublicDistributionListView,
    OnaharPublicLedgerView,
    OnaharStatsView,
)

app_name = 'onahar'

urlpatterns = [
    path('stats/', OnaharStatsView.as_view(), name='stats'),
    path('leaderboard/', OnaharLeaderboardView.as_view(), name='leaderboard'),
    path('ledger/', OnaharPublicLedgerView.as_view(), name='ledger'),
    path('distributions/', OnaharPublicDistributionListView.as_view(), name='distributions'),
    path(
        'distributions/<uuid:public_id>/',
        OnaharPublicDistributionDetailView.as_view(),
        name='distribution-detail',
    ),
    path('me/', OnaharMeView.as_view(), name='me'),
    path('me/history/', OnaharMeHistoryView.as_view(), name='me-history'),
    path('me/privacy/', OnaharMePrivacyView.as_view(), name='me-privacy'),
]
