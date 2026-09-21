from django.db.models import Count
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery_zones.api.serializers import (
    DeliveryLocationReorderSerializer,
    DeliveryLocationSerializer,
    DeliveryLocationUpdateSerializer,
    DeliveryLocationWriteSerializer,
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
from delivery_zones.services.priority import reorder_location_priorities
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
OPS_TAG = 'Admin Delivery Zone Ops'


class DeliveryZonePagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _error_response(exc, http_status=status.HTTP_422_UNPROCESSABLE_ENTITY):
    code = getattr(exc, 'code', 'DELIVERY_ZONE_ERROR')
    if code in {'ZONE_NOT_FOUND', 'LOCATION_NOT_FOUND', 'DELIVERY_MAN_NOT_FOUND'}:
        http_status = status.HTTP_404_NOT_FOUND
    elif code == 'UNSUPPORTED_FILTER':
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
        ).annotate(location_count=Count('locations'))
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
        zone = list_zones().filter(pk=zone.pk).annotate(location_count=Count('locations')).get()
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
        zone.location_count = zone.locations.count()
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
        zone.location_count = zone.locations.count()
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
        zone.location_count = zone.locations.count()
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
        zone.location_count = zone.locations.count()
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
        summary='Zone/location delivery counts and Delivery Man workload',
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
