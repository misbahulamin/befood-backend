from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from search.api.openapi import SEARCH_ADMIN_TAG, SEARCH_TAG
from search.api.serializers import (
    AnalyticsSummarySerializer,
    SearchClickSerializer,
    SearchDocumentAdminSerializer,
    SearchDocumentUpdateSerializer,
    SearchDocumentWriteSerializer,
    SearchKeywordSerializer,
    SearchKeywordWriteSerializer,
    SearchResponseSerializer,
    SuggestionResponseSerializer,
    document_to_card,
    normalize_session_id,
)
from search.models import SearchDocument, SearchKeyword
from search.services.analytics import record_click_event, record_query_event
from search.services.management import (
    SearchManagementError,
    create_document,
    create_document_keyword,
    deactivate_document,
    delete_document_keyword,
    update_document,
)
from search.services.popular import list_popular_searches
from search.services.queries import SearchQueryError, analytics_summary, filter_documents
from search.services.ranking import rank_documents, suggest_documents
from user_management.api.permissions import IsVerifiedAdmin


class SearchReadThrottle(AnonRateThrottle):
    rate = '120/min'


class SearchWriteThrottle(AnonRateThrottle):
    rate = '60/min'


class SearchUserReadThrottle(UserRateThrottle):
    rate = '240/min'


class SearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _error_response(exc, http_status=status.HTTP_400_BAD_REQUEST):
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': getattr(exc, 'errors', {}),
            'error_code': getattr(exc, 'code', 'SEARCH_ERROR'),
        },
        status=http_status,
    )


def _session_id_from_request(request, body_session: str = '') -> str:
    header = request.headers.get('X-Guest-Session-Id') or request.headers.get(
        'X-Session-Id', ''
    )
    return normalize_session_id(body_session or header)


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SearchReadThrottle, SearchUserReadThrottle]

    @extend_schema(
        tags=[SEARCH_TAG],
        operation_id='customerGlobalSearch',
        summary='Multilingual global catalog search',
        description=(
            'Normalize q then rank packages, instant meals, foods, and categories. '
            'Supports Bangla/Banglish/English keywords and fuzzy typo tolerance. '
            'Clients should debounce 250–350ms.'
        ),
        parameters=[
            OpenApiParameter(name='q', required=True, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
            OpenApiParameter(
                name='type',
                required=False,
                type=str,
                description='package | instant_meal | food | category',
            ),
            OpenApiParameter(name='session_id', required=False, type=str),
        ],
        responses={200: SearchResponseSerializer, 400: OpenApiResponse(description='Validation error')},
    )
    def get(self, request):
        raw_q = request.query_params.get('q')
        if raw_q is None:
            return Response(
                {
                    'success': False,
                    'message': 'Query parameter q is required.',
                    'errors': {'q': ['This field is required.']},
                    'error_code': 'VALIDATION_ERROR',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        doc_type = request.query_params.get('type') or None
        if doc_type and doc_type not in SearchDocument.DocumentType.values:
            return Response(
                {
                    'success': False,
                    'message': 'Unsupported type filter.',
                    'errors': {'type': ['Must be package, instant_meal, food, or category.']},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        outcome = rank_documents(
            raw_q,
            document_type=doc_type,
            limit=request.query_params.get('limit'),
        )
        results = [document_to_card(s.document) for s in outcome.results]
        related = [document_to_card(d) for d in outcome.related]
        payload = {
            'query': outcome.query_original,
            'query_normalized': outcome.query_normalized,
            'results': results,
            'did_you_mean': outcome.did_you_mean,
            'related': related,
        }

        if outcome.query_normalized:
            record_query_event(
                query_original=outcome.query_original,
                query_normalized=outcome.query_normalized,
                result_count=len(results),
                user=request.user,
                session_id=_session_id_from_request(
                    request,
                    request.query_params.get('session_id', ''),
                ),
            )
        return Response(payload)


class SearchSuggestionsView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SearchReadThrottle, SearchUserReadThrottle]

    @extend_schema(
        tags=[SEARCH_TAG],
        operation_id='customerSearchSuggestions',
        summary='Autocomplete suggestions (min 2 chars)',
        parameters=[
            OpenApiParameter(name='q', required=True, type=str),
            OpenApiParameter(name='limit', required=False, type=int),
            OpenApiParameter(name='type', required=False, type=str),
        ],
        responses={200: SuggestionResponseSerializer},
    )
    def get(self, request):
        raw_q = request.query_params.get('q')
        if raw_q is None:
            return Response(
                {
                    'success': False,
                    'message': 'Query parameter q is required.',
                    'errors': {'q': ['This field is required.']},
                    'error_code': 'VALIDATION_ERROR',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        doc_type = request.query_params.get('type') or None
        outcome = suggest_documents(
            raw_q,
            document_type=doc_type,
            limit=request.query_params.get('limit'),
        )
        return Response(
            {
                'query': outcome.query_original,
                'query_normalized': outcome.query_normalized,
                'results': [document_to_card(s.document, lean=True) for s in outcome.results],
            }
        )


class SearchPopularView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SearchReadThrottle, SearchUserReadThrottle]

    @extend_schema(
        tags=[SEARCH_TAG],
        operation_id='customerSearchPopular',
        summary='Popular / trending search terms',
        parameters=[OpenApiParameter(name='limit', required=False, type=int)],
        responses={200: OpenApiResponse(description='Popular terms')},
    )
    def get(self, request):
        return Response({'results': list_popular_searches(limit=request.query_params.get('limit'))})


class SearchClickEventView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SearchWriteThrottle]

    @extend_schema(
        tags=[SEARCH_TAG],
        operation_id='customerSearchClickEvent',
        summary='Record search result click',
        request=SearchClickSerializer,
        responses={201: OpenApiResponse(description='Click recorded')},
    )
    def post(self, request):
        serializer = SearchClickSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            document = SearchDocument.objects.get(public_id=data['public_id'], is_active=True)
        except SearchDocument.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Search result not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        event = record_click_event(
            document=document,
            query_original=data.get('query') or '',
            position=data.get('position'),
            user=request.user,
            session_id=_session_id_from_request(request, data.get('session_id', '')),
        )
        return Response(
            {
                'public_id': str(event.public_id),
                'clicked_type': event.clicked_type,
                'document_public_id': str(document.public_id),
            },
            status=status.HTTP_201_CREATED,
        )


class SearchDocumentAdminListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchDocumentList',
        parameters=[
            OpenApiParameter(name='document_type', required=False, type=str),
            OpenApiParameter(name='type', required=False, type=str),
            OpenApiParameter(name='is_active', required=False, type=bool),
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='page', required=False, type=int),
            OpenApiParameter(name='page_size', required=False, type=int),
        ],
        responses={200: SearchDocumentAdminSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_documents(request.query_params)
        except SearchQueryError as exc:
            return _error_response(exc)
        paginator = SearchPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            SearchDocumentAdminSerializer(page, many=True).data
        )

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchDocumentCreate',
        request=SearchDocumentWriteSerializer,
        responses={201: SearchDocumentAdminSerializer},
    )
    def post(self, request):
        serializer = SearchDocumentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = create_document(**serializer.validated_data)
        except SearchManagementError as exc:
            return _error_response(exc, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(
            SearchDocumentAdminSerializer(document).data,
            status=status.HTTP_201_CREATED,
        )


class SearchDocumentAdminDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    def _get(self, public_id):
        try:
            return SearchDocument.objects.prefetch_related('keywords').get(public_id=public_id)
        except SearchDocument.DoesNotExist:
            return None

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchDocumentRetrieve',
        responses={200: SearchDocumentAdminSerializer},
    )
    def get(self, request, public_id):
        document = self._get(public_id)
        if document is None:
            return Response(
                {
                    'success': False,
                    'message': 'Search document not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(SearchDocumentAdminSerializer(document).data)

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchDocumentUpdate',
        request=SearchDocumentUpdateSerializer,
        responses={200: SearchDocumentAdminSerializer},
    )
    def patch(self, request, public_id):
        document = self._get(public_id)
        if document is None:
            return Response(
                {
                    'success': False,
                    'message': 'Search document not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SearchDocumentUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        document = update_document(document, **serializer.validated_data)
        return Response(SearchDocumentAdminSerializer(document).data)

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchDocumentDeactivate',
        summary='Soft-delete (deactivate) a search document',
        responses={200: SearchDocumentAdminSerializer},
    )
    def delete(self, request, public_id):
        document = self._get(public_id)
        if document is None:
            return Response(
                {
                    'success': False,
                    'message': 'Search document not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        document = deactivate_document(document)
        return Response(SearchDocumentAdminSerializer(document).data)


class SearchDocumentKeywordListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    def _get_document(self, public_id):
        try:
            return SearchDocument.objects.get(public_id=public_id)
        except SearchDocument.DoesNotExist:
            return None

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchKeywordList',
        responses={200: SearchKeywordSerializer(many=True)},
    )
    def get(self, request, public_id):
        document = self._get_document(public_id)
        if document is None:
            return Response(
                {
                    'success': False,
                    'message': 'Search document not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            SearchKeywordSerializer(document.keywords.all(), many=True).data
        )

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchKeywordCreate',
        request=SearchKeywordWriteSerializer,
        responses={201: SearchKeywordSerializer},
    )
    def post(self, request, public_id):
        document = self._get_document(public_id)
        if document is None:
            return Response(
                {
                    'success': False,
                    'message': 'Search document not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SearchKeywordWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            keyword = create_document_keyword(document, **serializer.validated_data)
        except SearchManagementError as exc:
            return _error_response(exc, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        return Response(
            SearchKeywordSerializer(keyword).data,
            status=status.HTTP_201_CREATED,
        )


class SearchDocumentKeywordDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchKeywordDelete',
        responses={204: OpenApiResponse(description='Deleted')},
    )
    def delete(self, request, public_id, keyword_public_id):
        try:
            keyword = SearchKeyword.objects.select_related('document').get(
                public_id=keyword_public_id,
                document__public_id=public_id,
            )
        except SearchKeyword.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Keyword not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        delete_document_keyword(keyword)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SearchAdminAnalyticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SEARCH_ADMIN_TAG],
        operation_id='adminSearchAnalytics',
        parameters=[
            OpenApiParameter(name='from', required=False, type=str),
            OpenApiParameter(name='to', required=False, type=str),
        ],
        responses={200: AnalyticsSummarySerializer},
    )
    def get(self, request):
        try:
            data = analytics_summary(request.query_params)
        except SearchQueryError as exc:
            return _error_response(exc)
        return Response(AnalyticsSummarySerializer(data).data)
