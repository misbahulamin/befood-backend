from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin
from user_management.models import RiderProfile
from user_management.services.admin_deliveryman_360 import (
    DELIVERY_HISTORY_ALLOWLIST,
    LIST_QUERY_ALLOWLIST,
    RANKINGS_ALLOWLIST,
    ROUTE_ALLOWLIST,
    TIMELINE_ALLOWLIST,
    build_list_item,
    build_overview_payload,
    build_rankings,
    build_route_payload,
    business_today,
    get_rider_or_none,
    reject_unknown_params,
    rider_base_queryset,
    rider_deliveries_queryset,
    serialize_delivery_history_row,
    serialize_timeline_event,
    timeline_queryset,
)
from django.utils.dateparse import parse_date


class AdminDeliveryman360Pagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryMenList',
        summary='List Delivery Men with performance KPIs',
        parameters=[
            OpenApiParameter(name='q', required=False, type=str),
            OpenApiParameter(name='approval_status', required=False, type=str),
            OpenApiParameter(name='is_verified', required=False, type=bool),
        ],
        responses={200: OpenApiResponse(description='Paginated Delivery Man KPI list')},
    ),
    retrieve=extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryManOverview',
        summary='Lean Delivery Man 360 analytics overview',
        responses={
            200: OpenApiResponse(description='Overview with today/month/lifetime metrics'),
            404: OpenApiResponse(description='Not found'),
        },
    ),
)
class AdminDeliveryman360ViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    permission_classes = [IsVerifiedAdmin]
    pagination_class = AdminDeliveryman360Pagination
    lookup_field = 'public_id'
    queryset = RiderProfile.objects.none()

    def get_queryset(self):
        qs = rider_base_queryset().order_by('-created_at', 'public_id')
        params = self.request.query_params
        q = (params.get('q') or '').strip()
        if q:
            qs = qs.filter(
                models_q_search(q)
            )
        approval_status = params.get('approval_status')
        if approval_status:
            qs = qs.filter(approval_status=approval_status)
        is_verified = params.get('is_verified')
        if is_verified is not None:
            qs = qs.filter(is_verified=is_verified.lower() in {'1', 'true', 'yes'})
        return qs

    def list(self, request, *args, **kwargs):
        reject_unknown_params(request.query_params, LIST_QUERY_ALLOWLIST)
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        items = [build_list_item(rider) for rider in page]
        return self.get_paginated_response(items)

    def retrieve(self, request, *args, **kwargs):
        rider = get_rider_or_none(kwargs.get('public_id'))
        if rider is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(build_overview_payload(rider))

    @extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryManDeliveries',
        summary='Paginated delivery history for a Delivery Man',
        parameters=[
            OpenApiParameter(name='preset', required=False, type=str),
            OpenApiParameter(name='date_from', required=False, type=str),
            OpenApiParameter(name='date_to', required=False, type=str),
            OpenApiParameter(name='meal_period', required=False, type=str),
            OpenApiParameter(name='zone_public_id', required=False, type=str),
            OpenApiParameter(name='status', required=False, type=str),
            OpenApiParameter(name='logistics_status', required=False, type=str),
        ],
        responses={200: OpenApiResponse(description='Paginated delivery history')},
    )
    @action(detail=True, methods=['get'], url_path='deliveries')
    def deliveries(self, request, public_id=None):
        reject_unknown_params(request.query_params, DELIVERY_HISTORY_ALLOWLIST)
        rider = get_rider_or_none(public_id)
        if rider is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        qs = rider_deliveries_queryset(rider, request.query_params)
        page = self.paginate_queryset(qs)
        rows = [serialize_delivery_history_row(d) for d in page]
        return self.get_paginated_response(rows)

    @extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryManTimeline',
        summary='Activity timeline for a Delivery Man on a date',
        parameters=[OpenApiParameter(name='date', required=False, type=str)],
        responses={200: OpenApiResponse(description='Timeline events')},
    )
    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, public_id=None):
        reject_unknown_params(request.query_params, TIMELINE_ALLOWLIST)
        rider = get_rider_or_none(public_id)
        if rider is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        raw_date = request.query_params.get('date')
        if raw_date:
            event_date = parse_date(raw_date)
            if event_date is None:
                raise ValidationError({'date': ['Invalid date; use YYYY-MM-DD.']})
        else:
            event_date = business_today()
        qs = timeline_queryset(rider, event_date)
        page = self.paginate_queryset(qs)
        events = [serialize_timeline_event(e) for e in (page if page is not None else qs)]
        if page is not None:
            return self.get_paginated_response(events)
        return Response({'date': event_date.isoformat(), 'results': events})

    @extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryManRoute',
        summary='Ordered route stops for a meal window',
        parameters=[
            OpenApiParameter(name='service_date', required=True, type=str),
            OpenApiParameter(name='meal_period', required=True, type=str),
        ],
        responses={200: OpenApiResponse(description='Route sequence payload')},
    )
    @action(detail=True, methods=['get'], url_path='route')
    def route(self, request, public_id=None):
        reject_unknown_params(request.query_params, ROUTE_ALLOWLIST)
        rider = get_rider_or_none(public_id)
        if rider is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        service_date = parse_date(request.query_params.get('service_date') or '')
        meal_period = (request.query_params.get('meal_period') or '').strip()
        errors = {}
        if service_date is None:
            errors['service_date'] = ['This field is required (YYYY-MM-DD).']
        if meal_period not in {'lunch', 'dinner'}:
            errors['meal_period'] = ['Must be lunch or dinner.']
        if errors:
            raise ValidationError(errors)
        return Response(
            build_route_payload(rider, service_date=service_date, meal_period=meal_period)
        )

    @extend_schema(
        tags=['Admin Delivery Man 360'],
        operation_id='adminDeliveryMenRankings',
        summary='Compare Delivery Man performance for a period',
        parameters=[
            OpenApiParameter(name='preset', required=False, type=str),
            OpenApiParameter(name='date_from', required=False, type=str),
            OpenApiParameter(name='date_to', required=False, type=str),
        ],
        responses={200: OpenApiResponse(description='Rankings list')},
    )
    @action(detail=False, methods=['get'], url_path='rankings')
    def rankings(self, request):
        reject_unknown_params(request.query_params, RANKINGS_ALLOWLIST)
        rows = build_rankings(request.query_params)
        page = self.paginate_queryset(rows)
        if page is not None:
            return self.get_paginated_response(page)
        return Response({'results': rows})


def models_q_search(q: str):
    from django.db.models import Q

    return (
        Q(user__email__icontains=q)
        | Q(user__first_name__icontains=q)
        | Q(user__last_name__icontains=q)
        | Q(phone__icontains=q)
    )
