from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.guest_meal_serializers import (
    GuestMealOrderSerializer,
    GuestMealPreviewResponseSerializer,
    GuestMealRequestSerializer,
    GuestMealUsageSerializer,
)
from orders.api.permissions import IsVerifiedCustomer
from orders.models import GuestMealOrder
from orders.services.guest_meal import (
    GuestMealError,
    GuestMealNotEligibleError,
    GuestMealQuotaError,
    GuestMealValidationError,
    GuestMealWalletError,
    create_guest_meal_order,
    guest_usage_summary,
    preview_guest_meal,
    serialize_guest_meal_order,
)

GUEST_MEAL_TAG = 'Guest Meals'


class GuestMealPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _guest_meal_error_response(exc: GuestMealError) -> Response:
    payload = {'detail': str(exc), 'error_code': getattr(exc, 'code', 'GUEST_MEAL_ERROR')}
    if isinstance(exc, GuestMealValidationError) and exc.code == 'IDEMPOTENCY_CONFLICT':
        return Response(payload, status=status.HTTP_409_CONFLICT)
    if isinstance(
        exc,
        (
            GuestMealNotEligibleError,
            GuestMealQuotaError,
            GuestMealWalletError,
            GuestMealValidationError,
        ),
    ):
        return Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(payload, status=status.HTTP_400_BAD_REQUEST)


class GuestMealUsageView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[GUEST_MEAL_TAG],
        summary='Guest meal monthly usage',
        description=(
            'Returns the authenticated customer\'s countable guest meal quantity for the '
            'current Asia/Dhaka calendar month, plus configured monthly_limit and remaining.'
        ),
        responses={
            200: GuestMealUsageSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
        examples=[
            OpenApiExample(
                'Usage',
                value={
                    'calendar_month': '2026-09',
                    'monthly_limit': 10,
                    'used_quantity': 6,
                    'remaining_quantity': 4,
                },
                response_only=True,
            ),
        ],
    )
    def get(self, request):
        return Response(guest_usage_summary(request.user.customer_profile))


class GuestMealPreviewView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[GUEST_MEAL_TAG],
        summary='Preview guest meal pricing and eligibility',
        description=(
            'Read-only quote for a guest meal. Does not debit the wallet or create a record. '
            'Create always revalidates; never treat preview as authorization.'
        ),
        request=GuestMealRequestSerializer,
        responses={
            200: GuestMealPreviewResponseSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            422: OpenApiResponse(description='Not eligible / validation / quota / wallet floor'),
        },
        examples=[
            OpenApiExample(
                'Preview request',
                value={'date': '2026-09-30', 'meal_period': 'lunch', 'quantity': 2},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = GuestMealRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = preview_guest_meal(
                request.user.customer_profile,
                service_date=serializer.validated_data['date'],
                meal_period=serializer.validated_data['meal_period'],
                quantity=serializer.validated_data['quantity'],
            )
        except GuestMealError as exc:
            return _guest_meal_error_response(exc)
        return Response(payload)


class GuestMealListCreateView(APIView):
    permission_classes = [IsVerifiedCustomer]
    pagination_class = GuestMealPagination

    @extend_schema(
        tags=[GUEST_MEAL_TAG],
        summary='List own guest meal orders',
        responses={
            200: GuestMealOrderSerializer(many=True),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
    )
    def get(self, request):
        qs = (
            GuestMealOrder.objects.filter(customer=request.user.customer_profile)
            .select_related('subscription', 'delivery', 'wallet_transaction')
            .order_by('-created_at', '-id')
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [serialize_guest_meal_order(order) for order in page]
        return paginator.get_paginated_response(data)

    @extend_schema(
        tags=[GUEST_MEAL_TAG],
        summary='Create a prepaid guest meal order',
        description=(
            'Validates eligibility, enforces monthly quota and meal-stop recharge floor, '
            'debits the wallet (PAYMENT / commission_first), and creates a GuestMealOrder. '
            'Optional Idempotency-Key header replays the original result for the same payload.'
        ),
        request=GuestMealRequestSerializer,
        parameters=[
            OpenApiParameter(
                name='Idempotency-Key',
                type=str,
                location=OpenApiParameter.HEADER,
                required=False,
                description='Optional client retry key (scoped per customer).',
            ),
        ],
        responses={
            201: GuestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            409: OpenApiResponse(description='Idempotency key conflict'),
            422: OpenApiResponse(description='Not eligible / validation / quota / wallet'),
        },
        examples=[
            OpenApiExample(
                'Create request',
                value={'date': '2026-09-30', 'meal_period': 'lunch', 'quantity': 1},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = GuestMealRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get('Idempotency-Key') or request.META.get(
            'HTTP_IDEMPOTENCY_KEY'
        )
        try:
            _order, payload = create_guest_meal_order(
                request.user.customer_profile,
                service_date=serializer.validated_data['date'],
                meal_period=serializer.validated_data['meal_period'],
                quantity=serializer.validated_data['quantity'],
                idempotency_key=idempotency_key,
            )
        except GuestMealError as exc:
            return _guest_meal_error_response(exc)
        http_status = status.HTTP_200_OK if payload.get('idempotent_replay') else status.HTTP_201_CREATED
        return Response(payload, status=http_status)


class GuestMealDetailView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[GUEST_MEAL_TAG],
        summary='Get own guest meal order detail',
        responses={
            200: GuestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        order = (
            GuestMealOrder.objects.filter(
                customer=request.user.customer_profile,
                public_id=public_id,
            )
            .select_related('subscription', 'delivery', 'wallet_transaction')
            .first()
        )
        if order is None:
            return Response({'detail': 'Guest meal not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(serialize_guest_meal_order(order))
