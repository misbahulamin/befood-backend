from django.urls import path

from search.api.views import (
    GlobalSearchView,
    SearchClickEventView,
    SearchPopularView,
    SearchSuggestionsView,
)

app_name = 'search'

urlpatterns = [
    path('', GlobalSearchView.as_view(), name='global'),
    path('suggestions/', SearchSuggestionsView.as_view(), name='suggestions'),
    path('popular/', SearchPopularView.as_view(), name='popular'),
    path('events/click/', SearchClickEventView.as_view(), name='click-event'),
]
