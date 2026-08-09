from django.urls import path

from search.api.views import (
    SearchAdminAnalyticsView,
    SearchDocumentAdminDetailView,
    SearchDocumentAdminListCreateView,
    SearchDocumentKeywordDetailView,
    SearchDocumentKeywordListCreateView,
)

app_name = 'web_search'

urlpatterns = [
    path('documents/', SearchDocumentAdminListCreateView.as_view(), name='documents'),
    path(
        'documents/<uuid:public_id>/',
        SearchDocumentAdminDetailView.as_view(),
        name='document-detail',
    ),
    path(
        'documents/<uuid:public_id>/keywords/',
        SearchDocumentKeywordListCreateView.as_view(),
        name='document-keywords',
    ),
    path(
        'documents/<uuid:public_id>/keywords/<uuid:keyword_public_id>/',
        SearchDocumentKeywordDetailView.as_view(),
        name='document-keyword-detail',
    ),
    path('analytics/', SearchAdminAnalyticsView.as_view(), name='analytics'),
]
