from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from service_area.api.openapi import (
    CHECK_AVAILABLE_EXAMPLE,
    CHECK_LOW_ACCURACY_EXAMPLE,
    CHECK_UNAVAILABLE_EXAMPLE,
    ERROR_EXAMPLE,
    SERVICE_AREA_ADMIN_TAG,
    SERVICE_AREA_TAG,
)
from service_area.api.serializers import (
    AnalyticsSummarySerializer,
    ServiceAreaAdminSerializer,
    ServiceAreaAdminUpdateSerializer,
    ServiceAreaAdminWriteSerializer,
    ServiceAreaCheckResponseSerializer,
    ServiceAreaCheckSerializer,
    ServiceAreaRequestSerializer,
    ServiceAreaStatusSerializer,
)
from service_area.models import ServiceArea
from service_area.services.management import (
    ServiceAreaManagementError,
    create_service_area,
    soft_delete_service_area,
    set_service_area_active,
    update_service_area,
)
from service_area.services.queries import (
    ServiceAreaQueryError,
    analytics_summary,
    filter_requests,
    filter_service_areas,
)
from service_area.services.verification import (
    ServiceAreaError,
    check_service_area,
    record_demand,
)
from user_management.api.permissions import IsVerifiedAdmin


class ServiceAreaPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _error_response(exc, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY):
    code = getattr(exc, 'code', 'SERVICE_AREA_ERROR')
    if code == 'UNSUPPORTED_FILTER':
        http_status = status.HTTP_400_BAD_REQUEST
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': {},
            'error_code': code,
        },
        status=http_status,
    )


def _guest_session_id(request, body_value: str = '') -> str:
    header = request.headers.get('X-Guest-Session-Id') or request.headers.get(
        'x-guest-session-id'
    )
    return (body_value or header or '').strip()


def _customer_profile(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    return getattr(user, 'customer_profile', None)


def _run_location_action(request, *, demand: bool = False):
    serializer = ServiceAreaCheckSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    guest_id = _guest_session_id(request, data.get('guest_session_id', ''))
    location_name = data.get('location_name')
    if location_name is not None:
        location_name = location_name.strip() or None
    formatted = data.get('formatted_address')
    if formatted is not None:
        formatted = formatted.strip() or None

    kwargs = dict(
        latitude=data['latitude'],
        longitude=data['longitude'],
        accuracy=data.get('accuracy'),
        location_name=location_name,
        formatted_address=formatted,
        guest_session_id=guest_id,
        customer_profile=_customer_profile(request),
    )
    try:
        result = record_demand(**kwargs) if demand else check_service_area(**kwargs)
    except ValueError as exc:
        return _error_response(
            ServiceAreaError(str(exc), code='INVALID_COORDINATES'),
            http_status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except ServiceAreaError as exc:
        return _error_response(exc)
    return Response(result, status=status.HTTP_200_OK)


class ServiceAreaCheckView(APIView):
    """
    Coverage check from browser/device geolocation coordinates only.
    Does not use IP-based location.
    """

    permission_classes = [AllowAny]

    @extend_schema(
        tags=[SERVICE_AREA_TAG],
        operation_id='serviceAreaCheck',
        summary='Check if coordinates are inside an active BeFood service hub',
        description=(
            'Accepts latitude/longitude from browser/device geolocation (never IP). '
            'Readable location_name is optional display/analytics only. '
            'Persists a check history row for guests (guest_session_id) or customers.'
        ),
        request=ServiceAreaCheckSerializer,
        responses={
            200: OpenApiResponse(
                response=ServiceAreaCheckResponseSerializer,
                examples=[
                    OpenApiExample('available', value=CHECK_AVAILABLE_EXAMPLE),
                    OpenApiExample('unavailable', value=CHECK_UNAVAILABLE_EXAMPLE),
                    OpenApiExample('low_accuracy', value=CHECK_LOW_ACCURACY_EXAMPLE),
                ],
            ),
            422: OpenApiResponse(description='Validation / domain error', examples=[
                OpenApiExample('error', value=ERROR_EXAMPLE),
            ]),
        },
    )
    def post(self, request):
        return _run_location_action(request, demand=False)


class ServiceAreaDemandView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=[SERVICE_AREA_TAG],
        operation_id='serviceAreaDemand',
        summary='Record demand for BeFood in a non-covered (or any) location',
        request=ServiceAreaCheckSerializer,
        responses={200: ServiceAreaCheckResponseSerializer},
    )
    def post(self, request):
        return _run_location_action(request, demand=True)


class ServiceAreaAdminListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaList',
        summary='List service hubs',
        parameters=[
            OpenApiParameter(name='is_active', required=False, type=bool),
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='page', required=False, type=int),
            OpenApiParameter(name='page_size', required=False, type=int),
        ],
        responses={200: ServiceAreaAdminSerializer(many=True)},
    )
    def get(self, request):
        qs = filter_service_areas(request.query_params)
        paginator = ServiceAreaPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = ServiceAreaAdminSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaCreate',
        summary='Create a service hub',
        request=ServiceAreaAdminWriteSerializer,
        responses={201: ServiceAreaAdminSerializer, 422: OpenApiResponse(description='Error')},
    )
    def post(self, request):
        serializer = ServiceAreaAdminWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = getattr(request.user, 'admin_profile', None)
        try:
            area = create_service_area(created_by=admin, **serializer.validated_data)
        except ServiceAreaManagementError as exc:
            return _error_response(exc)
        return Response(
            ServiceAreaAdminSerializer(area).data,
            status=status.HTTP_201_CREATED,
        )


class ServiceAreaAdminDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    def _get(self, public_id):
        try:
            return ServiceArea.objects.select_related('created_by', 'created_by__user').get(
                public_id=public_id
            )
        except ServiceArea.DoesNotExist:
            return None

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaRetrieve',
        responses={200: ServiceAreaAdminSerializer, 404: OpenApiResponse(description='Not found')},
    )
    def get(self, request, public_id):
        area = self._get(public_id)
        if area is None:
            return Response(
                {
                    'success': False,
                    'message': 'Service area not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ServiceAreaAdminSerializer(area).data)

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaUpdate',
        request=ServiceAreaAdminUpdateSerializer,
        responses={200: ServiceAreaAdminSerializer},
    )
    def patch(self, request, public_id):
        area = self._get(public_id)
        if area is None:
            return Response(
                {
                    'success': False,
                    'message': 'Service area not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ServiceAreaAdminUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            area = update_service_area(area, **serializer.validated_data)
        except ServiceAreaManagementError as exc:
            return _error_response(exc)
        return Response(ServiceAreaAdminSerializer(area).data)

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaDelete',
        summary='Soft-delete (deactivate) a service hub',
        responses={200: ServiceAreaAdminSerializer},
    )
    def delete(self, request, public_id):
        area = self._get(public_id)
        if area is None:
            return Response(
                {
                    'success': False,
                    'message': 'Service area not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        area = soft_delete_service_area(area)
        return Response(ServiceAreaAdminSerializer(area).data)


class ServiceAreaAdminStatusView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaSetStatus',
        request=ServiceAreaStatusSerializer,
        responses={200: ServiceAreaAdminSerializer},
    )
    def post(self, request, public_id):
        try:
            area = ServiceArea.objects.get(public_id=public_id)
        except ServiceArea.DoesNotExist:
            return Response(
                {
                    'success': False,
                    'message': 'Service area not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ServiceAreaStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        area = set_service_area_active(area, serializer.validated_data['is_active'])
        return Response(ServiceAreaAdminSerializer(area).data)


class ServiceAreaAdminRequestListView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaRequestList',
        parameters=[
            OpenApiParameter(name='from', required=False, type=str),
            OpenApiParameter(name='to', required=False, type=str),
            OpenApiParameter(name='is_serviceable', required=False, type=bool),
            OpenApiParameter(name='request_kind', required=False, type=str),
            OpenApiParameter(name='q', required=False, type=str),
        ],
        responses={200: ServiceAreaRequestSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_requests(request.query_params)
        except ServiceAreaQueryError as exc:
            return _error_response(exc)
        paginator = ServiceAreaPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            ServiceAreaRequestSerializer(page, many=True).data
        )


class ServiceAreaAdminAnalyticsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SERVICE_AREA_ADMIN_TAG],
        operation_id='adminServiceAreaAnalytics',
        parameters=[
            OpenApiParameter(name='from', required=False, type=str),
            OpenApiParameter(name='to', required=False, type=str),
        ],
        responses={200: AnalyticsSummarySerializer},
    )
    def get(self, request):
        try:
            data = analytics_summary(request.query_params)
        except ServiceAreaQueryError as exc:
            return _error_response(exc)
        return Response(AnalyticsSummarySerializer(data).data)
