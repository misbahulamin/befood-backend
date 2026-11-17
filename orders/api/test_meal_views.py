from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
)
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.permissions import IsVerifiedCustomer
from orders.api.test_meal_serializers import (
    TestMealCreateSerializer,
    TestMealEligibilitySerializer,
    TestMealFunnelEventSerializer,
    TestMealOrderSerializer,
    TestMealPackageSerializer,
    TestMealQuoteRequestSerializer,
    TestMealQuoteResponseSerializer,
)
from orders.services.test_meal import (
    TestMealError,
    TestMealNotEligibleError,
    TestMealQuotaError,
    TestMealValidationError,
    build_test_meal_quote,
    create_test_meal_order,
    customer_test_meal_queryset,
    eligibility_for_customer,
    ingest_funnel_event,
    list_test_meal_packages,
    quote_to_dict,
    serialize_test_meal_order,
)

TEST_MEAL_TAG = 'Test Meals'


class TestMealPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


def _test_meal_error_response(exc: TestMealError) -> Response:
    payload = {
        'detail': str(exc),
        'error_code': getattr(exc, 'code', 'TEST_MEAL_ERROR'),
    }
    if isinstance(exc, TestMealValidationError) and exc.code == 'IDEMPOTENCY_CONFLICT':
        return Response(payload, status=status.HTTP_409_CONFLICT)
    if isinstance(
        exc,
        (
            TestMealNotEligibleError,
            TestMealQuotaError,
            TestMealValidationError,
        ),
    ):
        return Response(payload, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response(payload, status=status.HTTP_400_BAD_REQUEST)


class TestMealEligibilityView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='Test Meal eligibility and quota',
        description=(
            'Returns whether the authenticated customer can order a Test Meal, their '
            'lifetime quota usage, block reason/messages, currency, and delivery windows.'
        ),
        responses={
            200: TestMealEligibilitySerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
    )
    def get(self, request):
        return Response(eligibility_for_customer(request.user.customer_profile))


class TestMealPackageListView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='List orderable Test Meal packages',
        responses={
            200: TestMealPackageSerializer(many=True),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
    )
    def get(self, request):
        packages = list_test_meal_packages()
        data = [
            {
                'public_id': str(pkg.public_id),
                'name': pkg.meal_name,
                'meal_name': pkg.meal_name,
            }
            for pkg in packages
        ]
        return Response(data)


class TestMealQuoteView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='Preview Test Meal pricing',
        description=(
            'Read-only quote for a Test Meal. Revalidates eligibility, cutoff and published '
            'price but does not create a record. Create always revalidates; never treat a '
            'quote as authorization.'
        ),
        request=TestMealQuoteRequestSerializer,
        responses={
            200: TestMealQuoteResponseSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            422: OpenApiResponse(description='Not eligible / validation error'),
        },
        examples=[
            OpenApiExample(
                'Quote request',
                value={
                    'service_date': '2026-09-30',
                    'meal_period': 'lunch',
                    'package_public_id': '00000000-0000-0000-0000-000000000000',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = TestMealQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            quote = build_test_meal_quote(
                request.user.customer_profile,
                service_date=serializer.validated_data['service_date'],
                meal_period=serializer.validated_data['meal_period'],
                package_public_id=serializer.validated_data['package_public_id'],
            )
        except TestMealError as exc:
            return _test_meal_error_response(exc)
        return Response(quote_to_dict(quote))


class TestMealOrderListCreateView(APIView):
    permission_classes = [IsVerifiedCustomer]
    pagination_class = TestMealPagination

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='List own Test Meal orders',
        responses={
            200: TestMealOrderSerializer(many=True),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
    )
    def get(self, request):
        qs = customer_test_meal_queryset(request.user.customer_profile)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [serialize_test_meal_order(order) for order in page]
        return paginator.get_paginated_response(data)

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='Create a Test Meal order',
        description=(
            'Validates eligibility and lifetime quota, the service slot/cutoff, published '
            'price, and a resolvable owned delivery address. Creates a TestMealOrder and a '
            'linked fulfillment stop (no wallet debit). Optional Idempotency-Key header '
            'replays the original result for the same payload.'
        ),
        request=TestMealCreateSerializer,
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
            201: TestMealOrderSerializer,
            200: TestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            409: OpenApiResponse(description='Idempotency key conflict'),
            422: OpenApiResponse(description='Not eligible / validation / quota error'),
        },
        examples=[
            OpenApiExample(
                'Create request',
                value={
                    'service_date': '2026-09-30',
                    'meal_period': 'lunch',
                    'package_public_id': '00000000-0000-0000-0000-000000000000',
                    'address_public_id': '00000000-0000-0000-0000-000000000000',
                    'special_instructions': '',
                    'source_channel': 'mobile_app',
                },
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = TestMealCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        idempotency_key = request.headers.get('Idempotency-Key') or request.META.get(
            'HTTP_IDEMPOTENCY_KEY'
        )
        try:
            _order, payload = create_test_meal_order(
                request.user.customer_profile,
                service_date=serializer.validated_data['service_date'],
                meal_period=serializer.validated_data['meal_period'],
                package_public_id=serializer.validated_data['package_public_id'],
                address_public_id=serializer.validated_data['address_public_id'],
                special_instructions=serializer.validated_data.get(
                    'special_instructions', ''
                ),
                source_channel=serializer.validated_data.get('source_channel', ''),
                idempotency_key=idempotency_key,
            )
        except TestMealError as exc:
            return _test_meal_error_response(exc)
        http_status = (
            status.HTTP_200_OK
            if payload.get('idempotent_replay')
            else status.HTTP_201_CREATED
        )
        return Response(payload, status=http_status)


class TestMealOrderDetailView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='Get own Test Meal order detail',
        responses={
            200: TestMealOrderSerializer,
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            404: OpenApiResponse(description='Not found'),
        },
    )
    def get(self, request, public_id):
        order = customer_test_meal_queryset(request.user.customer_profile).filter(
            public_id=public_id
        ).first()
        if order is None:
            return Response(
                {'detail': 'Test Meal order not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_test_meal_order(order))


class TestMealFunnelEventView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=[TEST_MEAL_TAG],
        summary='Record a Test Meal funnel event',
        description=(
            'Deduped client instrumentation for the Test Meal funnel. Replays with the same '
            'client_event_id return 200; a new event returns 201.'
        ),
        request=TestMealFunnelEventSerializer,
        responses={
            201: OpenApiResponse(description='Event recorded'),
            200: OpenApiResponse(description='Duplicate event ignored'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            422: OpenApiResponse(description='Invalid event payload'),
        },
    )
    def post(self, request):
        serializer = TestMealFunnelEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            _event, created = ingest_funnel_event(
                event_name=serializer.validated_data['event_name'],
                client_event_id=serializer.validated_data['client_event_id'],
                customer=request.user.customer_profile,
                correlation_id=serializer.validated_data.get('correlation_id', ''),
                metadata=serializer.validated_data.get('metadata') or {},
            )
        except TestMealError as exc:
            return _test_meal_error_response(exc)
        payload = {'recorded': True, 'created': created}
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(payload, status=http_status)
