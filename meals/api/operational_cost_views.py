from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from user_management.api.permissions import IsVerifiedAdmin

from ..filters import OperationalCostMonthFilter
from ..models import OperationalCostMonth
from ..services.operational_cost_items import replace_operational_cost_items
from .operational_cost_serializers import (
    OperationalCostItemBulkSerializer,
    OperationalCostItemSerializer,
    OperationalCostMonthSerializer,
)


def _django_validation_to_response(exc: DjangoValidationError):
    if hasattr(exc, 'message_dict'):
        return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)
    if hasattr(exc, 'messages'):
        return Response({'detail': exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    list=extend_schema(
        tags=['Admin Operational Cost'],
        summary='List operational cost months',
        description=(
            'Verified-admin only. Returns monthly ledgers with items, '
            'total_operational_cost, and per_meal_operational_cost.'
        ),
    ),
    retrieve=extend_schema(
        tags=['Admin Operational Cost'],
        summary='Retrieve operational cost month',
    ),
    create=extend_schema(
        tags=['Admin Operational Cost'],
        summary='Create operational cost month',
        description=(
            'Create a month with target_meal_quantity. Optionally pass items_payload '
            'to seed cost lines in the same request.'
        ),
    ),
    partial_update=extend_schema(
        tags=['Admin Operational Cost'],
        summary='Update operational cost month',
    ),
    destroy=extend_schema(
        tags=['Admin Operational Cost'],
        summary='Delete operational cost month',
        responses={204: OpenApiResponse(description='Operational cost month deleted')},
    ),
)
class OperationalCostMonthViewSet(viewsets.ModelViewSet):
    queryset = OperationalCostMonth.objects.prefetch_related('items').all()
    serializer_class = OperationalCostMonthSerializer
    lookup_field = 'public_id'
    lookup_url_kwarg = 'public_id'
    permission_classes = [IsVerifiedAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = OperationalCostMonthFilter
    ordering_fields = ['year', 'month', 'created_at']
    ordering = ['-year', '-month']
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    @extend_schema(
        tags=['Admin Operational Cost'],
        summary='Replace all operational cost items for a month',
        request=OperationalCostItemBulkSerializer,
        responses={200: OperationalCostItemSerializer(many=True)},
    )
    @action(detail=True, methods=['put'], url_path='items')
    def replace_items(self, request, public_id=None):
        month = self.get_object()
        serializer = OperationalCostItemBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            items = replace_operational_cost_items(month, serializer.validated_data['items'])
        except DjangoValidationError as exc:
            return _django_validation_to_response(exc)
        return Response(OperationalCostItemSerializer(items, many=True).data)
