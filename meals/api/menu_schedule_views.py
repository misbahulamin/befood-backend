from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.api.permissions import IsVerifiedCustomer
from user_management.api.permissions import IsVerifiedAdmin

from meals.filters import MonthlyMenuScheduleFilter
from meals.models import MonthlyMenuSchedule
from meals.services.menu_schedule import (
    build_quota_summary,
    publish_schedule,
    replace_schedule_assignments,
    serialize_schedule_assignments,
    unpublish_schedule,
)
from meals.services.menu_sync import apply_sync_suggestion, sync_suggestion_response
from meals.services.package_menu import (
    build_order_menu_preview_for_meal,
    build_package_menu_for_customer,
)
from meals.services.today_menu import (
    build_today_menu_for_customer,
    get_reveal_settings,
    update_reveal_settings,
)
from .menu_schedule_serializers import (
    MenuAssignmentBulkSerializer,
    MenuRevealSettingsSerializer,
    MenuSyncApplySerializer,
    MenuSyncRequestSerializer,
    MonthlyMenuScheduleSerializer,
    MonthlyMenuScheduleUpdateSerializer,
)


def _django_validation_to_response(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    if hasattr(exc, 'messages'):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Menu Schedule'], summary='List monthly menu schedules'),
    retrieve=extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Retrieve monthly menu schedule',
    ),
    create=extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Create monthly menu schedule from finalized cycle plan',
    ),
    partial_update=extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Update monthly menu schedule notes',
    ),
    destroy=extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Delete monthly menu schedule',
        responses={204: OpenApiResponse(description='Schedule deleted')},
    ),
)
class MonthlyMenuScheduleViewSet(viewsets.ModelViewSet):
    queryset = MonthlyMenuSchedule.objects.select_related(
        'plan__cycle',
        'plan__meal_category',
    ).prefetch_related(
        'plan__lines__ingredient',
        'slots__items__ingredient',
    )
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MonthlyMenuScheduleFilter
    ordering_fields = ['created_at', 'status', 'published_at']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'patch', 'put', 'delete', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return MonthlyMenuScheduleUpdateSerializer
        return MonthlyMenuScheduleSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            schedule = serializer.save()
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        out = MonthlyMenuScheduleSerializer(schedule, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        schedule = self.get_object()
        if schedule.is_published:
            return Response(
                {'status': ['Published schedules cannot be deleted. Unpublish first.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Replace full-month slot assignments',
        request=MenuAssignmentBulkSerializer,
        responses={200: MonthlyMenuScheduleSerializer},
    )
    @action(detail=True, methods=['put'], url_path='assignments')
    def assignments(self, request, public_id=None):
        schedule = self.get_object()
        serializer = MenuAssignmentBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            schedule = replace_schedule_assignments(
                schedule,
                serializer.validated_data['assignments'],
            )
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        schedule = self.get_queryset().get(pk=schedule.pk)
        return Response(MonthlyMenuScheduleSerializer(schedule).data)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Quota usage summary for schedule',
        responses={200: OpenApiResponse(description='Per-ingredient quota usage')},
    )
    @action(detail=True, methods=['get'], url_path='quota-summary')
    def quota_summary(self, request, public_id=None):
        schedule = self.get_object()
        return Response(
            {
                'schedule_id': schedule.id,
                'items': build_quota_summary(schedule),
                'assignments': serialize_schedule_assignments(schedule),
            }
        )

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Publish monthly menu schedule',
        request=None,
        responses={200: MonthlyMenuScheduleSerializer},
    )
    @action(detail=True, methods=['post'], url_path='publish')
    def publish(self, request, public_id=None):
        schedule = self.get_object()
        try:
            schedule = publish_schedule(schedule)
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        schedule = self.get_queryset().get(pk=schedule.pk)
        return Response(MonthlyMenuScheduleSerializer(schedule).data)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Unpublish monthly menu schedule',
        request=None,
        responses={200: MonthlyMenuScheduleSerializer},
    )
    @action(detail=True, methods=['post'], url_path='unpublish')
    def unpublish(self, request, public_id=None):
        schedule = self.get_object()
        try:
            schedule = unpublish_schedule(schedule)
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        schedule = self.get_queryset().get(pk=schedule.pk)
        return Response(MonthlyMenuScheduleSerializer(schedule).data)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Build cross-package sync suggestions from a source schedule',
        request=MenuSyncRequestSerializer,
        responses={200: OpenApiResponse(description='Suggested assignments for this target')},
    )
    @action(detail=True, methods=['post'], url_path='sync-suggestions')
    def sync_suggestions(self, request, public_id=None):
        target = self.get_object()
        serializer = MenuSyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            source = MonthlyMenuSchedule.objects.select_related(
                'plan__cycle',
                'plan__meal_category',
            ).prefetch_related(
                'plan__lines__ingredient',
                'slots__items__ingredient',
            ).get(public_id=serializer.validated_data['source_schedule_id'])
        except MonthlyMenuSchedule.DoesNotExist:
            return Response(
                {'source_schedule_id': ['Source schedule not found.']},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            payload = sync_suggestion_response(source, target)
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(payload)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Apply sync suggestion to this draft schedule',
        request=MenuSyncApplySerializer,
        responses={200: MonthlyMenuScheduleSerializer},
    )
    @action(detail=True, methods=['post'], url_path='apply-sync')
    def apply_sync(self, request, public_id=None):
        target = self.get_object()
        serializer = MenuSyncApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = None
        source_id = serializer.validated_data.get('source_schedule_id')
        if source_id is not None:
            try:
                source = MonthlyMenuSchedule.objects.select_related(
                    'plan__cycle',
                    'plan__meal_category',
                ).prefetch_related(
                    'plan__lines__ingredient',
                    'slots__items__ingredient',
                ).get(public_id=source_id)
            except MonthlyMenuSchedule.DoesNotExist:
                return Response(
                    {'source_schedule_id': ['Source schedule not found.']},
                    status=status.HTTP_404_NOT_FOUND,
                )
        try:
            schedule = apply_sync_suggestion(
                target,
                source=source,
                assignments=serializer.validated_data.get('assignments'),
            )
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        schedule = self.get_queryset().get(pk=schedule.pk)
        return Response(MonthlyMenuScheduleSerializer(schedule).data)


class MenuRevealSettingsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Get menu reveal settings',
        responses={200: MenuRevealSettingsSerializer},
    )
    def get(self, request):
        settings_obj = get_reveal_settings()
        return Response(MenuRevealSettingsSerializer(settings_obj).data)

    @extend_schema(
        tags=['Admin Meal Menu Schedule'],
        summary='Update menu reveal settings',
        request=MenuRevealSettingsSerializer,
        responses={200: MenuRevealSettingsSerializer},
    )
    def patch(self, request):
        settings_obj = get_reveal_settings()
        serializer = MenuRevealSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        updated = update_reveal_settings(
            timezone_name=serializer.validated_data.get('timezone'),
            lunch_reveal_time=serializer.validated_data.get('lunch_reveal_time'),
            dinner_reveal_time=serializer.validated_data.get('dinner_reveal_time'),
        )
        return Response(MenuRevealSettingsSerializer(updated).data)


class CustomerTodayMenuView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Today Menu'],
        summary="Get today's menu for the customer's active meal packages",
        responses={200: OpenApiResponse(description="Today's visible meal periods")},
    )
    def get(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None and not (request.user.is_superuser or request.user.is_staff):
            # Verified admin without customer profile: empty eligible packages
            return Response(
                {
                    'service_date': None,
                    'packages': [],
                    'detail': 'No customer profile on this account.',
                }
            )
        if profile is None:
            return Response(
                {'detail': 'Customer profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(build_today_menu_for_customer(profile))


class CustomerPackageMenuView(APIView):
    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Package Menu'],
        summary="Get the full monthly menu for the customer's meal package(s)",
        description=(
            'Returns all published lunch/dinner slots for the target month for each '
            'of the caller\'s non-cancelled orders. Does not apply today-menu reveal-time gating. '
            'Omit year and month to use the current local month; provide both together to select a month.'
        ),
        parameters=[
            OpenApiParameter(
                name='year',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Calendar year (required together with month).',
            ),
            OpenApiParameter(
                name='month',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Calendar month 1–12 (required together with year).',
            ),
        ],
        responses={
            200: OpenApiResponse(
                description='Year/month and packages with full day slots or empty unpublished state'
            ),
            400: OpenApiResponse(description='Invalid year/month query'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer profile required'),
        },
    )
    def get(self, request):
        profile = getattr(request.user, 'customer_profile', None)
        if profile is None and not (request.user.is_superuser or request.user.is_staff):
            return Response(
                {
                    'year': None,
                    'month': None,
                    'packages': [],
                    'detail': 'No customer profile on this account.',
                }
            )
        if profile is None:
            return Response(
                {'detail': 'Customer profile required.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            payload = build_package_menu_for_customer(
                profile,
                year=request.query_params.get('year'),
                month=request.query_params.get('month'),
            )
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(payload)


class CustomerOrderMenuPreviewView(APIView):
    """Pre-order published menu preview by meal_public_id (no existing order required)."""

    permission_classes = [IsVerifiedCustomer]

    @extend_schema(
        tags=['Customer Package Menu'],
        summary='Preview published monthly menu before ordering',
        description=(
            'Returns the published lunch/dinner menu for a meal package and calendar month '
            'without requiring an existing order. Use during Order Now after month selection. '
            'If the menu is not published, responds 200 with schedule_published=false and empty days. '
            'Ownership-scoped post-order calendar remains GET /meals/my-package-menu/.'
        ),
        parameters=[
            OpenApiParameter(
                name='meal_public_id',
                type=str,
                location=OpenApiParameter.QUERY,
                required=True,
                description='Meal package public UUID',
            ),
            OpenApiParameter(
                name='year',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Calendar year (required together with month; default = current month)',
            ),
            OpenApiParameter(
                name='month',
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description='Calendar month 1-12 (required together with year)',
            ),
        ],
        responses={
            200: OpenApiResponse(description='Preview payload with schedule_published flag'),
            400: OpenApiResponse(description='Invalid year/month or missing meal_public_id'),
            401: OpenApiResponse(description='Authentication required'),
            403: OpenApiResponse(description='Verified customer required'),
            404: OpenApiResponse(description='Meal not found'),
        },
    )
    def get(self, request):
        meal_public_id = request.query_params.get('meal_public_id')
        if not meal_public_id:
            return Response(
                {'meal_public_id': ['This query parameter is required.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from meals.models import MealCategory

        try:
            meal = MealCategory.objects.get(public_id=meal_public_id)
        except (MealCategory.DoesNotExist, ValueError):
            return Response({'detail': 'Meal not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            payload = build_order_menu_preview_for_meal(
                meal,
                year=request.query_params.get('year'),
                month=request.query_params.get('month'),
            )
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(payload)
