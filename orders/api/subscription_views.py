from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from meals.models import MealCategory
from orders.api.permissions import IsVerifiedCustomer
from orders.api.serializers import MarkDeliverySerializer, MealOffRequestSerializer, MealOnRequestSerializer, OrderDeliverySerializer
from orders.filters import CustomerSubscriptionFilter
from orders.models import CustomerSubscription, OrderDelivery
from orders.services.meal_off import MealOffError, customer_meal_off, customer_meal_on
from orders.services.order_delivery import DeliveryError, mark_delivery_and_notify
from orders.services.subscription_service import (
    cancel_subscription,
    ensure_subscription_deliveries,
    get_active_subscription,
)
from user_management.api.permissions import IsVerifiedAdmin
from user_management.services.admin_access import is_verified_admin

from .subscription_serializers import (
    AdminSubscriptionDetailSerializer,
    AdminSubscriptionListSerializer,
    AdminSubscriptionPlanSerializer,
    CancelSubscriptionSerializer,
    CustomerSubscriptionDetailSerializer,
    CustomerSubscriptionPlanSerializer,
    CustomerSubscriptionSerializer,
    SubscribeSerializer,
)


class SubscriptionPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CustomerSubscriptionPlanViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = CustomerSubscriptionPlanSerializer
    permission_classes = [IsVerifiedCustomer]
    lookup_field = 'public_id'
    pagination_class = None
    queryset = MealCategory.objects.filter(is_active=True, is_subscribable=True).order_by('meal_name')

    @extend_schema(
        tags=['Meal Subscriptions'],
        summary='List available subscription plans',
        responses={200: CustomerSubscriptionPlanSerializer(many=True)},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


@extend_schema_view(
    create=extend_schema(
        tags=['Meal Subscriptions'],
        summary='Subscribe to a meal plan',
        request=SubscribeSerializer,
        responses={
            201: CustomerSubscriptionDetailSerializer,
            400: OpenApiResponse(description='Validation / wallet / already subscribed'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
        },
        examples=[
            OpenApiExample(
                'Subscribe',
                value={'plan_public_id': 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'},
                request_only=True,
            ),
        ],
    ),
    retrieve=extend_schema(
        tags=['Meal Subscriptions'],
        summary='Get own subscription detail',
        responses={
            200: CustomerSubscriptionDetailSerializer,
            404: OpenApiResponse(description='Not found'),
        },
    ),
)
class CustomerSubscriptionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [IsVerifiedCustomer]
    lookup_field = 'public_id'
    queryset = CustomerSubscription.objects.select_related(
        'meal', 'customer', 'customer__user'
    ).prefetch_related('deliveries')

    def get_serializer_class(self):
        if self.action == 'create':
            return SubscribeSerializer
        if self.action == 'retrieve':
            return CustomerSubscriptionDetailSerializer
        if self.action == 'cancel':
            return CancelSubscriptionSerializer
        return CustomerSubscriptionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if is_verified_admin(user) or user.is_superuser:
            return qs
        profile = getattr(user, 'customer_profile', None)
        if profile is None:
            return qs.none()
        return qs.filter(customer=profile)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        output = CustomerSubscriptionDetailSerializer(
            subscription, context={'request': request}
        )
        return Response(output.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=['Meal Subscriptions'],
        summary='Get current active subscription',
        responses={200: OpenApiResponse(description='Current subscription or null')},
    )
    @action(detail=False, methods=['get'], url_path='current')
    def current(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None:
            return Response(
                {
                    'current_subscription': None,
                    'message': 'No active meal subscription.',
                }
            )
        subscription = get_active_subscription(profile)
        if subscription is None:
            return Response(
                {
                    'current_subscription': None,
                    'message': 'No active meal subscription.',
                }
            )
        ensure_subscription_deliveries(subscription)
        return Response(
            {
                'current_subscription': CustomerSubscriptionDetailSerializer(
                    subscription, context={'request': request}
                ).data,
                'message': None,
            }
        )

    @extend_schema(
        tags=['Meal Subscriptions'],
        summary='Cancel current active subscription',
        request=CancelSubscriptionSerializer,
        responses={
            200: CustomerSubscriptionSerializer,
            404: OpenApiResponse(description='No active subscription'),
        },
    )
    @action(detail=False, methods=['post'], url_path='current/cancel')
    def cancel_current(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        subscription = get_active_subscription(profile)
        if subscription is None:
            return Response(
                {'detail': 'No active meal subscription.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        updated = cancel_subscription(subscription)
        return Response(CustomerSubscriptionSerializer(updated, context={'request': request}).data)

    @extend_schema(
        tags=['Meal Subscriptions'],
        summary='Meal-off a subscription delivery slot',
        request=MealOffRequestSerializer,
        responses={200: OrderDeliverySerializer, 404: OpenApiResponse(description='Not found')},
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/meal-off',
    )
    def meal_off(self, request, public_id=None, delivery_id=None):
        subscription = self.get_object()
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None or subscription.customer_id != profile.pk:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            delivery = subscription.deliveries.get(public_id=delivery_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealOffRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = customer_meal_off(
                delivery,
                user=request.user,
                note=serializer.validated_data.get('note', ''),
            )
        except MealOffError as exc:
            message = str(exc)
            if 'not found' in message.lower():
                return Response({'detail': message}, status=status.HTTP_404_NOT_FOUND)
            code = (
                status.HTTP_409_CONFLICT
                if 'already' in message.lower()
                else status.HTTP_400_BAD_REQUEST
            )
            return Response({'detail': message}, status=code)
        return Response(OrderDeliverySerializer(updated).data)

    @extend_schema(
        tags=['Meal Subscriptions'],
        summary='Meal-on a customer-skipped subscription slot',
        request=MealOnRequestSerializer,
        responses={200: OrderDeliverySerializer},
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/meal-on',
    )
    def meal_on(self, request, public_id=None, delivery_id=None):
        subscription = self.get_object()
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None or subscription.customer_id != profile.pk:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        try:
            delivery = subscription.deliveries.get(public_id=delivery_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MealOnRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = customer_meal_on(
                delivery,
                user=request.user,
                note=serializer.validated_data.get('note', ''),
            )
        except MealOffError as exc:
            message = str(exc)
            if 'not found' in message.lower():
                return Response({'detail': message}, status=status.HTTP_404_NOT_FOUND)
            return Response({'detail': message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderDeliverySerializer(updated).data)


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Meal Subscriptions'],
        summary='List customer subscriptions',
        parameters=[
            OpenApiParameter(name='status', type=str, description='active|cancelled'),
            OpenApiParameter(name='plan_public_id', type=str, description='Meal plan UUID'),
            OpenApiParameter(name='started_after', type=str, description='YYYY-MM-DD'),
            OpenApiParameter(name='started_before', type=str, description='YYYY-MM-DD'),
        ],
        responses={200: AdminSubscriptionListSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Admin Meal Subscriptions'],
        summary='Subscription detail',
        responses={200: AdminSubscriptionDetailSerializer},
    ),
)
class AdminSubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsVerifiedAdmin]
    lookup_field = 'public_id'
    filter_backends = [DjangoFilterBackend]
    filterset_class = CustomerSubscriptionFilter
    pagination_class = SubscriptionPagination
    queryset = CustomerSubscription.objects.select_related(
        'meal', 'customer', 'customer__user'
    ).prefetch_related('deliveries')

    _ALLOWED_QUERY = {
        'status',
        'plan_public_id',
        'started_after',
        'started_before',
        'cancelled_after',
        'cancelled_before',
        'page',
        'page_size',
    }

    def list(self, request, *args, **kwargs):
        extra = set(request.query_params.keys()) - self._ALLOWED_QUERY
        if extra:
            return Response(
                {'detail': f'Unsupported filter(s): {", ".join(sorted(extra))}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        status_value = request.query_params.get('status')
        if status_value and status_value not in {
            CustomerSubscription.Status.ACTIVE,
            CustomerSubscription.Status.CANCELLED,
        }:
            return Response(
                {'status': ['Must be active or cancelled.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().list(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return AdminSubscriptionDetailSerializer
        return AdminSubscriptionListSerializer

    def retrieve(self, request, *args, **kwargs):
        subscription = self.get_object()
        if subscription.status == CustomerSubscription.Status.ACTIVE:
            ensure_subscription_deliveries(subscription)
            subscription.refresh_from_db()
        return Response(
            AdminSubscriptionDetailSerializer(subscription, context={'request': request}).data
        )

    @extend_schema(
        tags=['Admin Meal Subscriptions'],
        summary='Mark a subscription delivery delivered or skipped',
        request=MarkDeliverySerializer,
        responses={200: OrderDeliverySerializer},
    )
    @action(
        detail=True,
        methods=['post'],
        url_path=r'deliveries/(?P<delivery_id>[^/.]+)/mark',
    )
    def mark_delivery(self, request, public_id=None, delivery_id=None):
        subscription = self.get_object()
        try:
            delivery = subscription.deliveries.get(public_id=delivery_id)
        except (OrderDelivery.DoesNotExist, ValueError):
            return Response({'detail': 'Delivery not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = MarkDeliverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = mark_delivery_and_notify(
                delivery,
                to_status=serializer.validated_data['status'],
                marked_by=request.user,
                note=serializer.validated_data.get('note', ''),
            )
        except DeliveryError as exc:
            message = str(exc)
            payload = {'detail': message}
            if getattr(exc, 'code', None):
                payload['error_code'] = exc.code
            code = status.HTTP_409_CONFLICT if 'already' in message.lower() else status.HTTP_400_BAD_REQUEST
            if getattr(exc, 'code', None) in {
                'WALLET_INSUFFICIENT_FOR_MEAL',
                'WALLET_FROZEN',
                'MEAL_PAYMENT_IDEMPOTENCY_CONFLICT',
                'MEAL_PAYMENT_FAILED',
                'MEAL_SLOT_PRICE_MISSING',
            }:
                code = status.HTTP_422_UNPROCESSABLE_ENTITY
            return Response(payload, status=code)
        return Response(OrderDeliverySerializer(updated).data)


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Subscriptions'], summary='List subscription plans'),
    create=extend_schema(tags=['Admin Meal Subscriptions'], summary='Create a subscription plan'),
    retrieve=extend_schema(tags=['Admin Meal Subscriptions'], summary='Get a subscription plan'),
    partial_update=extend_schema(
        tags=['Admin Meal Subscriptions'], summary='Update a subscription plan'
    ),
)
class AdminSubscriptionPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsVerifiedAdmin]
    serializer_class = AdminSubscriptionPlanSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    lookup_field = 'public_id'
    http_method_names = ['get', 'post', 'patch', 'head', 'options']
    queryset = MealCategory.objects.all().order_by('-created_at')

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == 'list' and self.request.query_params.get('subscribable_only') == 'true':
            return qs.filter(is_subscribable=True)
        return qs
