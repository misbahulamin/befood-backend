from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from ..filters import (
    IngredientFilter,
    MealCycleFilter,
    MealCyclePlanFilter,
    MealCyclePlanLineFilter,
)
from ..models import Ingredient, MealCycle, MealCyclePlan, MealCyclePlanLine
from ..services.cycle_calculations import (
    build_plan_summary,
    finalize_plan,
    reopen_plan,
    replace_plan_lines,
)
from .cycle_serializers import (
    IngredientSerializer,
    MealCyclePlanLineBulkSerializer,
    MealCyclePlanLineSerializer,
    MealCyclePlanSerializer,
    MealCycleSerializer,
)


def _django_validation_to_response(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    if hasattr(exc, 'messages'):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Cycle'], summary='List ingredients'),
    retrieve=extend_schema(tags=['Admin Meal Cycle'], summary='Retrieve ingredient detail'),
    create=extend_schema(tags=['Admin Meal Cycle'], summary='Create ingredient'),
    partial_update=extend_schema(tags=['Admin Meal Cycle'], summary='Update ingredient'),
    destroy=extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Delete ingredient',
        responses={204: OpenApiResponse(description='Ingredient deleted')},
    ),
)
class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = IngredientFilter
    ordering_fields = ['name', 'price_per_kg', 'created_at', 'product_role']
    ordering = ['name']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Cycle'], summary='List meal cycles'),
    retrieve=extend_schema(tags=['Admin Meal Cycle'], summary='Retrieve meal cycle'),
    create=extend_schema(tags=['Admin Meal Cycle'], summary='Create meal cycle'),
    partial_update=extend_schema(tags=['Admin Meal Cycle'], summary='Update meal cycle notes'),
    destroy=extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Delete meal cycle',
        responses={204: OpenApiResponse(description='Meal cycle deleted')},
    ),
)
class MealCycleViewSet(viewsets.ModelViewSet):
    queryset = MealCycle.objects.all()
    serializer_class = MealCycleSerializer
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MealCycleFilter
    ordering_fields = ['year', 'month', 'created_at']
    ordering = ['-year', '-month']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Cycle'], summary='List meal cycle plans'),
    retrieve=extend_schema(tags=['Admin Meal Cycle'], summary='Retrieve meal cycle plan'),
    create=extend_schema(tags=['Admin Meal Cycle'], summary='Create meal cycle plan'),
    partial_update=extend_schema(tags=['Admin Meal Cycle'], summary='Update meal cycle plan'),
    destroy=extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Delete meal cycle plan',
        responses={204: OpenApiResponse(description='Meal cycle plan deleted')},
    ),
)
class MealCyclePlanViewSet(viewsets.ModelViewSet):
    queryset = MealCyclePlan.objects.select_related('cycle', 'meal_category').prefetch_related(
        'lines__ingredient'
    )
    serializer_class = MealCyclePlanSerializer
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MealCyclePlanFilter
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan.is_finalized:
            return Response(
                {'status': ['Finalized plans cannot be deleted. Reopen first.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Get cycle plan cost summary',
        responses={200: OpenApiResponse(description='Plan summary with line and package totals')},
    )
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        plan = self.get_object()
        return Response(build_plan_summary(plan))

    @extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Finalize cycle plan',
        request=None,
        responses={200: OpenApiResponse(description='Finalized plan summary')},
    )
    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None):
        plan = self.get_object()
        try:
            plan = finalize_plan(plan)
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(build_plan_summary(plan))

    @extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Reopen finalized cycle plan',
        request=None,
        responses={200: MealCyclePlanSerializer},
    )
    @action(detail=True, methods=['post'], url_path='reopen')
    def reopen(self, request, pk=None):
        plan = self.get_object()
        try:
            plan = reopen_plan(plan)
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        serializer = self.get_serializer(plan)
        return Response(serializer.data)

    @extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Replace all servings lines for a plan',
        request=MealCyclePlanLineBulkSerializer,
        responses={200: MealCyclePlanLineSerializer(many=True)},
    )
    @action(detail=True, methods=['put'], url_path='lines')
    def replace_lines(self, request, pk=None):
        plan = self.get_object()
        serializer = MealCyclePlanLineBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            lines = replace_plan_lines(plan, serializer.validated_data['lines'])
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(MealCyclePlanLineSerializer(lines, many=True).data)


@extend_schema_view(
    list=extend_schema(tags=['Admin Meal Cycle'], summary='List cycle plan lines'),
    retrieve=extend_schema(tags=['Admin Meal Cycle'], summary='Retrieve cycle plan line'),
    create=extend_schema(tags=['Admin Meal Cycle'], summary='Create cycle plan line'),
    partial_update=extend_schema(tags=['Admin Meal Cycle'], summary='Update cycle plan line'),
    destroy=extend_schema(
        tags=['Admin Meal Cycle'],
        summary='Delete cycle plan line',
        responses={204: OpenApiResponse(description='Plan line deleted')},
    ),
)
class MealCyclePlanLineViewSet(viewsets.ModelViewSet):
    queryset = MealCyclePlanLine.objects.select_related('plan', 'ingredient', 'plan__cycle')
    serializer_class = MealCyclePlanLineSerializer
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = MealCyclePlanLineFilter
    ordering_fields = ['servings_count', 'created_at']
    ordering = ['ingredient__name']
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def destroy(self, request, *args, **kwargs):
        line = self.get_object()
        if line.plan.is_finalized:
            return Response(
                {'plan': ['Finalized plans cannot be edited. Reopen the plan first.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)
