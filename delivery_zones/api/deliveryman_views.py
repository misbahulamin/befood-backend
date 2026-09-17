from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from delivery_zones.api.serializers import (
    DeliverymanBoardQuerySerializer,
    DeliverymanMarkDeliverySerializer,
)
from delivery_zones.services.board import build_deliveryman_board, delivery_in_rider_zone
from delivery_zones.services.errors import DeliveryZoneError
from orders.models import OrderDelivery
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
            'params are ignored (BREAKING vs dual-period board).'
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
            OpenApiParameter(name='include_delivered', required=False, type=bool),
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

        to_status = serializer.validated_data['status']
        try:
            updated = mark_delivery_and_notify(
                delivery,
                to_status=to_status,
                marked_by=request.user,
                note=serializer.validated_data.get('note', ''),
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
