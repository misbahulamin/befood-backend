from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery_zones.models import DeliverySubLocation

from delivery_zones.api.serializers import (
    DeliveryLocationReorderSerializer,
    DeliveryLocationSerializer,
    DeliveryLocationUpdateSerializer,
    DeliveryLocationWriteSerializer,
    DeliverySubLocationReorderSerializer,
    DeliverySubLocationSerializer,
    DeliverySubLocationUpdateSerializer,
    DeliverySubLocationWriteSerializer,
    DeliveryZoneAssignRiderSerializer,
    DeliveryZoneSerializer,
    DeliveryZoneUpdateSerializer,
    DeliveryZoneWriteSerializer,
)
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.locations import (
    create_location,
    delete_location_if_empty,
    get_location_by_public_id,
    list_locations,
    update_location,
)
from delivery_zones.services.geo_analytics import build_geo_analytics_matrix
from delivery_zones.services.ops import build_ops_summary, parse_ops_query
from delivery_zones.services.priority import (
    reorder_location_priorities,
    reorder_sub_location_priorities,
)
from delivery_zones.services.sub_locations import (
    create_sub_location,
    delete_sub_location_if_empty,
    get_sub_location_by_public_id,
    list_sub_locations,
    update_sub_location,
)
from delivery_zones.services.zones import (
    assign_delivery_man,
    clear_delivery_man,
    create_zone,
    deactivate_zone,
    delete_zone_if_empty,
    get_zone_by_public_id,
    list_zones,
    update_zone,
)
from user_management.api.permissions import IsVerifiedAdmin


ZONE_TAG = 'Admin Delivery Zones'
LOCATION_TAG = 'Admin Delivery Locations'
SUB_LOCATION_TAG = 'Admin Delivery Sub-Locations'
OPS_TAG = 'Admin Delivery Zone Ops'
ANALYTICS_TAG = 'Admin Delivery Geo Analytics'


class DeliveryZonePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _attach_zone_counts(zone) -> None:
    zone.location_count = zone.locations.count()
    zone.sub_location_count = DeliverySubLocation.objects.filter(location__zone=zone).count()


def _error_response(exc, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY):
    code = getattr(exc, 'code', 'DELIVERY_ZONE_ERROR')
    if code in {
        'ZONE_NOT_FOUND',
        'LOCATION_NOT_FOUND',
        'SUB_LOCATION_NOT_FOUND',
        'DELIVERY_MAN_NOT_FOUND',
    }:
        http_status = status.HTTP_404_NOT_FOUND
    elif code in {
        'UNSUPPORTED_FILTER',
        'DATE_RANGE_REQUIRED',
        'INVALID_DATE',
        'INVALID_DATE_RANGE',
        'DATE_RANGE_TOO_LONG',
        'INVALID_MEAL_PERIOD',
        'INVALID_PUBLIC_ID',
        'SERVICE_DATE_REQUIRED',
        'INVALID_SERVICE_DATE',
        'MEAL_PERIOD_REQUIRED',
    }:
        http_status = status.HTTP_400_BAD_REQUEST
    elif code == 'DELIVERY_MAN_ALREADY_ASSIGNED':
        http_status = status.HTTP_409_CONFLICT
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': {},
            'error_code': code,
        },
        status=http_status,
    )


class DeliveryZoneListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneList',
        summary='List delivery zones',
        parameters=[
            OpenApiParameter(name='status', required=False, type=str),
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='page', required=False, type=int),
            OpenApiParameter(name='page_size', required=False, type=int),
        ],
        responses={200: DeliveryZoneSerializer(many=True)},
    )
    def get(self, request):
        qs = list_zones(
            status=request.query_params.get('status') or None,
            q=request.query_params.get('q') or None,
        ).annotate(
            location_count=Count('locations', distinct=True),
            sub_location_count=Count('locations__sub_locations', distinct=True),
        )
        paginator = DeliveryZonePagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliveryZoneSerializer(page, many=True).data
        )

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneCreate',
        summary='Create a delivery zone',
        request=DeliveryZoneWriteSerializer,
        responses={201: DeliveryZoneSerializer, 422: OpenApiResponse(description='Error')},
    )
    def post(self, request):
        serializer = DeliveryZoneWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            zone = create_zone(**serializer.validated_data)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        zone = (
            list_zones()
            .filter(pk=zone.pk)
            .annotate(
                location_count=Count('locations', distinct=True),
                sub_location_count=Count('locations__sub_locations', distinct=True),
            )
            .get()
        )
        return Response(DeliveryZoneSerializer(zone).data, status=status.HTTP_201_CREATED)


class DeliveryZoneDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneRetrieve',
        responses={200: DeliveryZoneSerializer, 404: OpenApiResponse(description='Not found')},
    )
    def get(self, request, public_id):
        try:
            zone = get_zone_by_public_id(public_id)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        _attach_zone_counts(zone)
        return Response(DeliveryZoneSerializer(zone).data)

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneUpdate',
        request=DeliveryZoneUpdateSerializer,
        responses={200: DeliveryZoneSerializer},
    )
    def patch(self, request, public_id):
        try:
            zone = get_zone_by_public_id(public_id)
            serializer = DeliveryZoneUpdateSerializer(data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            zone = update_zone(zone, **serializer.validated_data)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        _attach_zone_counts(zone)
        return Response(DeliveryZoneSerializer(zone).data)

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneDelete',
        summary='Delete empty zone',
        responses={204: OpenApiResponse(description='Deleted'), 422: OpenApiResponse()},
    )
    def delete(self, request, public_id):
        try:
            zone = get_zone_by_public_id(public_id)
            delete_zone_if_empty(zone)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeliveryZoneAssignRiderView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneAssignRider',
        summary='Assign or clear primary Delivery Man',
        request=DeliveryZoneAssignRiderSerializer,
        responses={200: DeliveryZoneSerializer},
    )
    def patch(self, request, public_id):
        serializer = DeliveryZoneAssignRiderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            zone = get_zone_by_public_id(public_id)
            rider_id = serializer.validated_data.get('delivery_man_public_id')
            if rider_id is None:
                zone = clear_delivery_man(zone)
            else:
                zone = assign_delivery_man(zone, delivery_man_public_id=rider_id)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        _attach_zone_counts(zone)
        return Response(DeliveryZoneSerializer(zone).data)


class DeliveryZoneLocationReorderView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneLocationReorder',
        summary='Rewrite every location priority in a zone',
        request=DeliveryLocationReorderSerializer,
        responses={200: DeliveryLocationSerializer(many=True)},
    )
    def patch(self, request, public_id):
        serializer = DeliveryLocationReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            zone = get_zone_by_public_id(public_id)
            reorder_location_priorities(zone, serializer.validated_data['locations'])
        except DeliveryZoneError as exc:
            return _error_response(exc)
        locations = list_locations(zone_public_id=public_id)
        return Response(DeliveryLocationSerializer(locations, many=True).data)


class DeliveryZoneDeactivateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ZONE_TAG],
        operation_id='adminDeliveryZoneDeactivate',
        request=None,
        responses={200: DeliveryZoneSerializer},
    )
    def post(self, request, public_id):
        try:
            zone = deactivate_zone(get_zone_by_public_id(public_id))
        except DeliveryZoneError as exc:
            return _error_response(exc)
        _attach_zone_counts(zone)
        return Response(DeliveryZoneSerializer(zone).data)


class DeliveryLocationListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[LOCATION_TAG],
        operation_id='adminDeliveryLocationList',
        parameters=[
            OpenApiParameter(name='zone_public_id', required=False, type=str),
            OpenApiParameter(name='status', required=False, type=str),
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='page', required=False, type=int),
            OpenApiParameter(name='page_size', required=False, type=int),
        ],
        responses={200: DeliveryLocationSerializer(many=True)},
    )
    def get(self, request):
        qs = list_locations(
            zone_public_id=request.query_params.get('zone_public_id') or None,
            status=request.query_params.get('status') or None,
            q=request.query_params.get('q') or None,
        )
        paginator = DeliveryZonePagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliveryLocationSerializer(page, many=True).data
        )

    @extend_schema(
        tags=[LOCATION_TAG],
        operation_id='adminDeliveryLocationCreate',
        request=DeliveryLocationWriteSerializer,
        responses={201: DeliveryLocationSerializer},
    )
    def post(self, request):
        serializer = DeliveryLocationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            location = create_location(**serializer.validated_data)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(
            DeliveryLocationSerializer(location).data,
            status=status.HTTP_201_CREATED,
        )


class DeliveryLocationDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[LOCATION_TAG],
        operation_id='adminDeliveryLocationRetrieve',
        responses={200: DeliveryLocationSerializer},
    )
    def get(self, request, public_id):
        try:
            location = get_location_by_public_id(public_id)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(DeliveryLocationSerializer(location).data)

    @extend_schema(
        tags=[LOCATION_TAG],
        operation_id='adminDeliveryLocationUpdate',
        request=DeliveryLocationUpdateSerializer,
        responses={200: DeliveryLocationSerializer},
    )
    def patch(self, request, public_id):
        serializer = DeliveryLocationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            location = get_location_by_public_id(public_id)
            location = update_location(location, **serializer.validated_data)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(DeliveryLocationSerializer(location).data)

    @extend_schema(
        tags=[LOCATION_TAG],
        operation_id='adminDeliveryLocationDelete',
        responses={204: OpenApiResponse(description='Deleted')},
    )
    def delete(self, request, public_id):
        try:
            location = get_location_by_public_id(public_id)
            delete_location_if_empty(location)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeliveryZoneOpsSummaryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[OPS_TAG],
        operation_id='adminDeliveryZoneOpsSummary',
        summary='Zone/location/sub-location delivery counts and Delivery Man workload',
        parameters=[
            OpenApiParameter(name='service_date', required=True, type=str),
            OpenApiParameter(name='meal_period', required=True, type=str),
        ],
        responses={200: OpenApiResponse(description='Ops summary')},
    )
    def get(self, request):
        try:
            service_date, meal_period = parse_ops_query(request.query_params)
            payload = build_ops_summary(service_date=service_date, meal_period=meal_period)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(payload)


class DeliveryGeoAnalyticsMatrixView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[ANALYTICS_TAG],
        operation_id='adminDeliveryGeoAnalyticsMatrix',
        summary='Period geo analytics matrix (zone → location → sub-location)',
        description=(
            'Verified admin only. Required from/to (Asia/Dhaka, max 366 days). '
            'Optional meal_period and hierarchy filters. Rankings included in the same payload.'
        ),
        parameters=[
            OpenApiParameter(name='from', required=True, type=str),
            OpenApiParameter(name='to', required=True, type=str),
            OpenApiParameter(name='meal_period', required=False, type=str),
            OpenApiParameter(name='zone_public_id', required=False, type=str),
            OpenApiParameter(name='location_public_id', required=False, type=str),
            OpenApiParameter(name='sub_location_public_id', required=False, type=str),
        ],
        responses={200: OpenApiResponse(description='Geo analytics matrix + rankings')},
    )
    def get(self, request):
        try:
            payload = build_geo_analytics_matrix(request.query_params)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(payload)


class DeliverySubLocationListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliverySubLocationList',
        parameters=[
            OpenApiParameter(name='location_public_id', required=False, type=str),
            OpenApiParameter(name='zone_public_id', required=False, type=str),
            OpenApiParameter(name='status', required=False, type=str),
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='page', required=False, type=int),
            OpenApiParameter(name='page_size', required=False, type=int),
        ],
        responses={200: DeliverySubLocationSerializer(many=True)},
    )
    def get(self, request):
        qs = list_sub_locations(
            location_public_id=request.query_params.get('location_public_id') or None,
            zone_public_id=request.query_params.get('zone_public_id') or None,
            status=request.query_params.get('status') or None,
            q=request.query_params.get('q') or None,
        )
        paginator = DeliveryZonePagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            DeliverySubLocationSerializer(page, many=True).data
        )

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliverySubLocationCreate',
        request=DeliverySubLocationWriteSerializer,
        responses={201: DeliverySubLocationSerializer},
    )
    def post(self, request):
        serializer = DeliverySubLocationWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sub = create_sub_location(**serializer.validated_data)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        sub = get_sub_location_by_public_id(sub.public_id)
        return Response(
            DeliverySubLocationSerializer(sub).data,
            status=status.HTTP_201_CREATED,
        )


class DeliverySubLocationDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliverySubLocationRetrieve',
        responses={200: DeliverySubLocationSerializer},
    )
    def get(self, request, public_id):
        try:
            sub = get_sub_location_by_public_id(public_id)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(DeliverySubLocationSerializer(sub).data)

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliverySubLocationUpdate',
        request=DeliverySubLocationUpdateSerializer,
        responses={200: DeliverySubLocationSerializer},
    )
    def patch(self, request, public_id):
        serializer = DeliverySubLocationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            sub = get_sub_location_by_public_id(public_id)
            sub = update_sub_location(sub, **serializer.validated_data)
            sub = get_sub_location_by_public_id(sub.public_id)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(DeliverySubLocationSerializer(sub).data)

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliverySubLocationDelete',
        responses={204: OpenApiResponse(description='Deleted')},
    )
    def delete(self, request, public_id):
        try:
            sub = get_sub_location_by_public_id(public_id)
            delete_sub_location_if_empty(sub)
        except DeliveryZoneError as exc:
            return _error_response(exc)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeliveryLocationSubLocationReorderView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[SUB_LOCATION_TAG],
        operation_id='adminDeliveryLocationSubLocationReorder',
        summary='Rewrite every sub-location priority under a location',
        request=DeliverySubLocationReorderSerializer,
        responses={200: DeliverySubLocationSerializer(many=True)},
    )
    def patch(self, request, public_id):
        serializer = DeliverySubLocationReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            location = get_location_by_public_id(public_id)
            reorder_sub_location_priorities(
                location, serializer.validated_data['sub_locations']
            )
        except DeliveryZoneError as exc:
            return _error_response(exc)
        subs = list_sub_locations(location_public_id=public_id)
        return Response(DeliverySubLocationSerializer(subs, many=True).data)
