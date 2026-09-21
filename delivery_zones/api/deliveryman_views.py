from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery_zones.api.serializers import (
    DeliverymanBoardQuerySerializer,
    DeliverymanLogisticsTransitionSerializer,
    DeliverymanMarkDeliverySerializer,
)
from delivery_zones.services.board import build_deliveryman_board, delivery_in_rider_zone
from delivery_zones.services.errors import DeliveryZoneError
from delivery_zones.services.today_summary import build_deliveryman_today_summary
from orders.models import OrderDelivery
from orders.services.delivery_logistics import LogisticsError, transition_logistics_status
from orders.services.meal_demand import delivery_customer_is_meal_service_blocked
from orders.services.order_delivery import DeliveryError, mark_delivery_and_notify
from user_management.api.permissions import IsVerifiedDeliveryman


class DeliverymanTodayBoardView(APIView):
    permission_classes = [IsVerifiedDeliveryman]

    @extend_schema(
        tags=['Delivery Man Board'],
        operation_id='deliverymanTodayBoard',
        summary='Zone-scoped active-meal today delivery board',
        description=(
            'Returns only the server-resolved active meal period for business today '
            '(meal-off settings timezone). Client service_date and meal_period query '
            'params are ignored (BREAKING vs dual-period board).\n\n'
            'Use ``status=scheduled`` (default) for To Deliver, ``status=delivered`` '
            'for Delivered tab. ``include_delivered=true`` remains for legacy clients '
            '(scheduled+delivered) when ``status`` is omitted.'
        ),
        parameters=[
            OpenApiParameter(
                name='service_date',
                required=False,
                type=str,
                description='Ignored; board always uses meal-off business today.',
            ),
            OpenApiParameter(
                name='meal_period',
                required=False,
                type=str,
                description='Ignored; board always uses active meal window.',
            ),
            OpenApiParameter(
                name='status',
                required=False,
                type=str,
                description='scheduled | delivered | all. Takes precedence over include_delivered.',
            ),
            OpenApiParameter(
                name='include_delivered',
                required=False,
                type=bool,
                description='Legacy: when true and status omitted, include delivered rows.',
            ),
            OpenApiParameter(
                name='zone_public_id',
                required=False,
                type=str,
                description='Ignored; board is always scoped to the rider assigned zone.',
            ),
        ],
        responses={200: OpenApiResponse(description='Deliveryman board payload')},
    )
    def get(self, request):
        serializer = DeliverymanBoardQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = build_deliveryman_board(
                request.user.rider_profile,
                include_delivered=bool(data.get('include_delivered')),
                status=data.get('status'),
            )
        except DeliveryZoneError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': getattr(exc, 'code', 'DELIVERY_ZONE_ERROR'),
                },
                status=422,
            )
        return Response(payload)


class DeliverymanTodaySummaryView(APIView):
    permission_classes = [IsVerifiedDeliveryman]

    @extend_schema(
        tags=['Delivery Man Board'],
        operation_id='deliverymanTodaySummary',
        summary='Today delivery metrics and package breakdown for the rider zone',
        description=(
            'Stop-based total / delivered / pending for the active meal window, plus '
            'dynamic package counts from subscription/order meal snapshots. Same zone '
            'and meal-off timezone scope as today-board. Client date/period ignored.'
        ),
        parameters=[
            OpenApiParameter(
                name='service_date',
                required=False,
                type=str,
                description='Ignored; summary always uses meal-off business today.',
            ),
            OpenApiParameter(
                name='meal_period',
                required=False,
                type=str,
                description='Ignored; summary always uses active meal window.',
            ),
        ],
        responses={200: OpenApiResponse(description='Today summary payload')},
    )
    def get(self, request):
        # Accept (and ignore) same legacy query keys as the board for client symmetry.
        serializer = DeliverymanBoardQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        try:
            payload = build_deliveryman_today_summary(request.user.rider_profile)
        except DeliveryZoneError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': getattr(exc, 'code', 'DELIVERY_ZONE_ERROR'),
                },
                status=422,
            )
        return Response(payload)


class DeliverymanMarkDeliveryView(APIView):
    permission_classes = [IsVerifiedDeliveryman]

    @extend_schema(
        tags=['Delivery Man Board'],
        operation_id='deliverymanMarkDelivery',
        summary='Mark a zone delivery as delivered',
        request=DeliverymanMarkDeliverySerializer,
        responses={
            200: OpenApiResponse(description='Updated delivery'),
            403: OpenApiResponse(description='Not in rider zone'),
            404: OpenApiResponse(description='Not found'),
            409: OpenApiResponse(description='Conflict'),
            422: OpenApiResponse(description='Wallet / payment failure'),
        },
    )
    def post(self, request, delivery_public_id):
        serializer = DeliverymanMarkDeliverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delivery = OrderDelivery.objects.select_related(
                'order',
                'order__customer__delivery_location__zone',
                'subscription',
                'subscription__customer__delivery_location__zone',
            ).get(public_id=delivery_public_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found.'}, status=status.HTTP_404_NOT_FOUND)

        rider = request.user.rider_profile
        if not delivery_in_rider_zone(delivery, rider):
            return Response(
                {'detail': 'Delivery is not in your assigned zone.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Same low-balance meal-stop gate as auto_deliver_meals candidates.
        # Admin mark APIs intentionally omit this check (ops override).
        if delivery_customer_is_meal_service_blocked(delivery):
            return Response(
                {
                    'detail': (
                        'Customer meal service is paused due to low wallet balance; '
                        'delivery cannot be marked by deliveryman.'
                    ),
                    'error_code': 'MEAL_SERVICE_BLOCKED_LOW_BALANCE',
                },
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        to_status = serializer.validated_data['status']
        try:
            updated = mark_delivery_and_notify(
                delivery,
                to_status=to_status,
                marked_by=request.user,
                note=serializer.validated_data.get('note', ''),
                rider=rider,
                completion_latitude=serializer.validated_data.get('latitude'),
                completion_longitude=serializer.validated_data.get('longitude'),
                logistics_source='deliveryman',
            )
        except DeliveryError as exc:
            message = str(exc)
            payload = {'detail': message}
            if getattr(exc, 'code', None):
                payload['error_code'] = exc.code
            if getattr(exc, 'code', None) in {
                'WALLET_INSUFFICIENT_FOR_MEAL',
                'WALLET_FROZEN',
                'MEAL_PAYMENT_IDEMPOTENCY_CONFLICT',
                'MEAL_PAYMENT_FAILED',
                'MEAL_SLOT_PRICE_MISSING',
                'MEAL_SERVICE_BLOCKED_LOW_BALANCE',
            }:
                return Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
            # Already delivered (same status) is handled inside mark_delivery as idempotent.
            # Terminal conflict (e.g. skipped → delivered) → 409.
            code = (
                status.HTTP_409_CONFLICT
                if 'already' in message.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response(payload, status=code)

        return Response(
            {
                'delivery_public_id': str(updated.public_id),
                'status': updated.status,
                'marked_at': updated.marked_at.isoformat() if updated.marked_at else None,
                'payment_status': updated.payment_status,
            }
        )


class DeliverymanLogisticsTransitionView(APIView):
    """Phase B: intermediate logistics status transitions (not meal mark-delivered)."""

    permission_classes = [IsVerifiedDeliveryman]

    @extend_schema(
        tags=['Delivery Man Board'],
        operation_id='deliverymanLogisticsTransition',
        summary='Update logistics status for a zone delivery stop',
        description=(
            'Advances rider logistics status (accepted / picked_up / out_for_delivery / '
            'failed / cancelled). Meal delivered remains POST .../mark/. Phase A mark may '
            'jump to logistics delivered without intermediates.'
        ),
        request=DeliverymanLogisticsTransitionSerializer,
        responses={
            200: OpenApiResponse(description='Updated logistics state'),
            403: OpenApiResponse(description='Not in rider zone'),
            404: OpenApiResponse(description='Not found'),
            409: OpenApiResponse(description='Invalid transition'),
            422: OpenApiResponse(description='Validation / business rule failure'),
        },
    )
    def post(self, request, delivery_public_id):
        serializer = DeliverymanLogisticsTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            delivery = OrderDelivery.objects.select_related(
                'order',
                'order__customer__delivery_location__zone',
                'subscription',
                'subscription__customer__delivery_location__zone',
            ).get(public_id=delivery_public_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found.'}, status=status.HTTP_404_NOT_FOUND)

        rider = request.user.rider_profile
        if not delivery_in_rider_zone(delivery, rider):
            return Response(
                {'detail': 'Delivery is not in your assigned zone.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            updated = transition_logistics_status(
                delivery,
                serializer.validated_data['status'],
                rider=rider,
                latitude=serializer.validated_data.get('latitude'),
                longitude=serializer.validated_data.get('longitude'),
                source='deliveryman',
                note=serializer.validated_data.get('note', ''),
                allow_phase_a_deliver_shortcut=False,
            )
        except LogisticsError as exc:
            code = (
                status.HTTP_409_CONFLICT
                if getattr(exc, 'code', '') == 'INVALID_TRANSITION'
                else status.HTTP_422_UNPROCESSABLE_ENTITY
            )
            return Response(
                {'detail': str(exc), 'error_code': getattr(exc, 'code', 'LOGISTICS_ERROR')},
                status=code,
            )

        return Response(
            {
                'delivery_public_id': str(updated.public_id),
                'meal_status': updated.status,
                'logistics_status': updated.logistics_status,
                'assigned_at': updated.assigned_at.isoformat() if updated.assigned_at else None,
                'accepted_at': updated.accepted_at.isoformat() if updated.accepted_at else None,
                'picked_up_at': updated.picked_up_at.isoformat() if updated.picked_up_at else None,
                'out_for_delivery_at': (
                    updated.out_for_delivery_at.isoformat()
                    if updated.out_for_delivery_at
                    else None
                ),
                'delivered_at': (
                    updated.delivered_at.isoformat() if updated.delivered_at else None
                ),
                'failed_at': updated.failed_at.isoformat() if updated.failed_at else None,
            }
        )
