from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from inventory.api.openapi import (
    INSUFFICIENT_STOCK_EXAMPLE,
    INSUFFICIENT_WALLET_EXAMPLE,
    INVENTORY_TAG,
)
from inventory.api.serializers import (
    AdjustmentReadSerializer,
    AdjustmentSerializer,
    InventoryAuditLogSerializer,
    InventoryDashboardSerializer,
    InventoryItemSerializer,
    InventoryItemUpdateSerializer,
    InventoryItemWriteSerializer,
    InventoryPurchaseCreateSerializer,
    InventoryPurchaseSerializer,
    InventoryStockMovementSerializer,
    ItemDetailSerializer,
    KitchenUsageSerializer,
    StockIssueSerializer,
    WastageReadSerializer,
    WastageSerializer,
)
from inventory.models import (
    InventoryAuditLog,
    InventoryItem,
    InventoryKitchenUsage,
    InventoryPurchase,
)
from inventory.services.items import create_item, update_item
from inventory.services.ledger import InsufficientStockError, InventoryError
from inventory.services.operations import adjust_stock, issue_kitchen_usage, record_wastage
from inventory.services.purchasing import (
    attach_invoice,
    cancel_purchase,
    confirm_purchase,
    create_purchase,
)
from inventory.services.queries import (
    REPORT_KEYS,
    dashboard_payload,
    filter_audit_logs,
    filter_items,
    filter_purchases,
    filter_usages,
    report_rows,
)
from inventory.services.units import InventoryUnitError
from user_management.api.permissions import IsVerifiedAdmin


class InventoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# Business-rule failures (structurally valid input that violates domain rules).
_INVENTORY_UNPROCESSABLE_CODES = frozenset(
    {
        'INSUFFICIENT_STOCK',
        'INSUFFICIENT_WALLET_BALANCE',
        'DUPLICATE_ITEM_NAME',
        'INVALID_STATUS',
        'INVALID_MINIMUM_STOCK',
        'INVALID_QUANTITY',
        'INVALID_AMOUNT',
        'INVALID_UNIT',
        'UNSUPPORTED_UNIT',
        'INCOMPATIBLE_UNIT',
        'UNIT_LOCKED',
        'NAME_REQUIRED',
        'ITEM_REQUIRED',
        'LINES_REQUIRED',
        'REASON_REQUIRED',
        'PURCHASE_CANCELLED',
        'INVALID_PURCHASE_STATUS',
        'CANCEL_BLOCKED_STOCK_CONSUMED',
        'ADMIN_WALLET_ERROR',
        'INVENTORY_ERROR',
    }
)

# Malformed / allowlist / upload structural issues stay 400.
_INVENTORY_BAD_REQUEST_CODES = frozenset(
    {
        'UNSUPPORTED_FILTER',
        'UNSUPPORTED_REPORT',
        'INVOICE_REQUIRED',
        'INVALID_INVOICE_TYPE',
        'INVOICE_TOO_LARGE',
    }
)


def _error_response(exc, http_status=None):
    code = getattr(exc, 'code', 'INVENTORY_ERROR')
    if http_status is None:
        if code in _INVENTORY_BAD_REQUEST_CODES:
            http_status = status.HTTP_400_BAD_REQUEST
        elif code in _INVENTORY_UNPROCESSABLE_CODES:
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
        else:
            http_status = status.HTTP_422_UNPROCESSABLE_ENTITY
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': {},
            'error_code': code,
        },
        status=http_status,
    )


def _actor_admin(request):
    return getattr(request.user, 'admin_profile', None)


def _get_item_or_404(public_id):
    try:
        return InventoryItem.objects.get(public_id=public_id)
    except InventoryItem.DoesNotExist:
        return None


def _get_purchase_or_404(public_id):
    try:
        return InventoryPurchase.objects.prefetch_related('lines__item').get(
            public_id=public_id
        )
    except InventoryPurchase.DoesNotExist:
        return None


class InventoryDashboardView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryDashboard',
        summary='Inventory dashboard summary cards',
        responses={200: InventoryDashboardSerializer},
    )
    def get(self, request):
        payload = dashboard_payload()
        return Response(InventoryDashboardSerializer(payload).data)


class InventoryItemListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryItemList',
        summary='List inventory items',
        parameters=[
            OpenApiParameter('status', str),
            OpenApiParameter('category', str),
            OpenApiParameter('q', str),
            OpenApiParameter('low_stock', str),
            OpenApiParameter('out_of_stock', str),
        ],
        responses={200: InventoryItemSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_items(InventoryItem.objects.all(), request.query_params)
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            InventoryItemSerializer(page, many=True).data
        )

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryItemCreate',
        summary='Create inventory item',
        request=InventoryItemWriteSerializer,
        responses={201: InventoryItemSerializer},
    )
    def post(self, request):
        serializer = InventoryItemWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            item = create_item(
                name=data['name'],
                default_unit=data['default_unit'],
                category=data.get('category', ''),
                status=data.get('status', InventoryItem.Status.ACTIVE),
                minimum_stock_level=data.get('minimum_stock_level'),
                linked_ingredient=data.get('linked_ingredient_public_id'),
                created_by=_actor_admin(request),
            )
        except (InventoryError, InventoryUnitError) as exc:
            return _error_response(exc)
        return Response(
            InventoryItemSerializer(item).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryItemDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryItemDetail',
        summary='Inventory item detail with history summary',
        responses={200: ItemDetailSerializer},
    )
    def get(self, request, public_id):
        item = _get_item_or_404(public_id)
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(ItemDetailSerializer(item).data)

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryItemUpdate',
        summary='Update inventory item',
        request=InventoryItemUpdateSerializer,
        responses={200: InventoryItemSerializer},
    )
    def patch(self, request, public_id):
        item = _get_item_or_404(public_id)
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = InventoryItemUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        kwargs = {'actor_admin': _actor_admin(request)}
        for key in ('name', 'default_unit', 'category', 'status', 'minimum_stock_level'):
            if key in data:
                kwargs[key] = data[key]
        if 'linked_ingredient_public_id' in data:
            kwargs['linked_ingredient'] = data['linked_ingredient_public_id']
        try:
            item = update_item(item, **kwargs)
        except (InventoryError, InventoryUnitError) as exc:
            return _error_response(exc)
        return Response(InventoryItemSerializer(item).data)


class InventoryItemMovementsView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryItemMovements',
        summary='List stock movements for an item',
        responses={200: InventoryStockMovementSerializer(many=True)},
    )
    def get(self, request, public_id):
        item = _get_item_or_404(public_id)
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        qs = item.movements.select_related('actor_admin__user').all()
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            InventoryStockMovementSerializer(page, many=True).data
        )


class InventoryPurchaseListCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseList',
        summary='Purchase history',
        parameters=[
            OpenApiParameter('date_from', str),
            OpenApiParameter('date_to', str),
            OpenApiParameter('item', str),
            OpenApiParameter('admin', str),
            OpenApiParameter('category', str),
            OpenApiParameter('amount_min', str),
            OpenApiParameter('amount_max', str),
            OpenApiParameter('supplier', str),
            OpenApiParameter('status', str),
            OpenApiParameter('q', str),
        ],
        responses={200: InventoryPurchaseSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_purchases(
                InventoryPurchase.objects.prefetch_related('lines__item').select_related(
                    'created_by__user', 'wallet_transaction'
                ),
                request.query_params,
            )
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            InventoryPurchaseSerializer(
                page, many=True, context={'request': request}
            ).data
        )

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseCreate',
        summary='Create inventory purchase (optional confirm)',
        request=InventoryPurchaseCreateSerializer,
        responses={
            201: InventoryPurchaseSerializer,
            422: OpenApiResponse(
                description='Insufficient wallet or validation',
                examples=[
                    OpenApiExample('wallet', value=INSUFFICIENT_WALLET_EXAMPLE),
                ],
            ),
        },
    )
    def post(self, request):
        serializer = InventoryPurchaseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        line_payloads = []
        for line in data['lines']:
            item = _get_item_or_404(line['item_public_id'])
            if item is None:
                return Response(
                    {
                        'success': False,
                        'message': 'Inventory item not found.',
                        'errors': {'item_public_id': ['Not found']},
                        'error_code': 'ITEM_NOT_FOUND',
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
            line_payloads.append(
                {
                    'item': item,
                    'quantity': line['quantity'],
                    'unit': line.get('unit') or item.default_unit,
                    'line_total': line['line_total'],
                }
            )
        try:
            purchase = create_purchase(
                lines=line_payloads,
                actor_admin=_actor_admin(request),
                supplier=data.get('supplier', ''),
                note=data.get('note', ''),
                purchase_date=data.get('purchase_date'),
                confirm=data.get('confirm', False),
                invoice=data.get('invoice'),
            )
        except (InventoryError, InventoryUnitError, InsufficientStockError) as exc:
            return _error_response(exc)
        purchase = InventoryPurchase.objects.prefetch_related('lines__item').get(
            pk=purchase.pk
        )
        return Response(
            InventoryPurchaseSerializer(purchase, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryPurchaseDetailView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseDetail',
        summary='Purchase detail',
        responses={200: InventoryPurchaseSerializer},
    )
    def get(self, request, public_id):
        purchase = _get_purchase_or_404(public_id)
        if purchase is None:
            return Response(
                {
                    'success': False,
                    'message': 'Purchase not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            InventoryPurchaseSerializer(purchase, context={'request': request}).data
        )


class InventoryPurchaseConfirmView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseConfirm',
        summary='Confirm purchase (stock + wallet debit)',
        responses={
            200: InventoryPurchaseSerializer,
            422: OpenApiResponse(examples=[OpenApiExample('wallet', value=INSUFFICIENT_WALLET_EXAMPLE)]),
        },
    )
    def post(self, request, public_id):
        purchase = _get_purchase_or_404(public_id)
        if purchase is None:
            return Response(
                {
                    'success': False,
                    'message': 'Purchase not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            purchase = confirm_purchase(purchase, actor_admin=_actor_admin(request))
        except (InventoryError, InventoryUnitError) as exc:
            return _error_response(exc)
        purchase = InventoryPurchase.objects.prefetch_related('lines__item').get(
            pk=purchase.pk
        )
        return Response(
            InventoryPurchaseSerializer(purchase, context={'request': request}).data
        )


class InventoryPurchaseCancelView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseCancel',
        summary='Cancel purchase (draft discard or confirmed reversal)',
        responses={200: InventoryPurchaseSerializer},
    )
    def post(self, request, public_id):
        purchase = _get_purchase_or_404(public_id)
        if purchase is None:
            return Response(
                {
                    'success': False,
                    'message': 'Purchase not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        reason = request.data.get('reason', '') if isinstance(request.data, dict) else ''
        try:
            purchase = cancel_purchase(
                purchase,
                actor_admin=_actor_admin(request),
                reason=reason,
            )
        except (InventoryError, InventoryUnitError, InsufficientStockError) as exc:
            return _error_response(exc)
        purchase = InventoryPurchase.objects.prefetch_related('lines__item').get(
            pk=purchase.pk
        )
        return Response(
            InventoryPurchaseSerializer(purchase, context={'request': request}).data
        )


class InventoryPurchaseInvoiceView(APIView):
    permission_classes = [IsVerifiedAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryPurchaseInvoiceUpload',
        summary='Attach invoice/receipt to purchase',
        request=InventoryPurchaseCreateSerializer,
        responses={200: InventoryPurchaseSerializer},
    )
    def post(self, request, public_id):
        purchase = _get_purchase_or_404(public_id)
        if purchase is None:
            return Response(
                {
                    'success': False,
                    'message': 'Purchase not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        invoice = request.FILES.get('invoice')
        if not invoice:
            return Response(
                {
                    'success': False,
                    'message': 'Invoice file is required.',
                    'errors': {'invoice': ['Required']},
                    'error_code': 'INVOICE_REQUIRED',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        content_type = getattr(invoice, 'content_type', '') or ''
        name = (getattr(invoice, 'name', '') or '').lower()
        allowed = {'image/jpeg', 'image/png', 'application/pdf', 'image/jpg'}
        if content_type not in allowed and not name.endswith(
            ('.jpg', '.jpeg', '.png', '.pdf')
        ):
            return Response(
                {
                    'success': False,
                    'message': 'Invoice must be JPG, PNG, or PDF.',
                    'errors': {'invoice': ['Invalid type']},
                    'error_code': 'INVALID_INVOICE_TYPE',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if invoice.size > 10 * 1024 * 1024:
            return Response(
                {
                    'success': False,
                    'message': 'Invoice file must be at most 10MB.',
                    'errors': {'invoice': ['Too large']},
                    'error_code': 'INVOICE_TOO_LARGE',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            purchase = attach_invoice(
                purchase, invoice=invoice, actor_admin=_actor_admin(request)
            )
        except InventoryError as exc:
            return _error_response(exc)
        return Response(
            InventoryPurchaseSerializer(purchase, context={'request': request}).data
        )


class InventoryStockIssueView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryStockIssue',
        summary='Issue kitchen stock usage',
        request=StockIssueSerializer,
        responses={
            201: KitchenUsageSerializer,
            422: OpenApiResponse(
                examples=[OpenApiExample('stock', value=INSUFFICIENT_STOCK_EXAMPLE)]
            ),
        },
    )
    def post(self, request):
        serializer = StockIssueSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = _get_item_or_404(data['item_public_id'])
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            usage = issue_kitchen_usage(
                item=item,
                quantity=data['quantity'],
                unit=data.get('unit'),
                purpose=data.get('purpose', ''),
                menu_reference=data.get('menu_reference', ''),
                kitchen_batch=data.get('kitchen_batch', ''),
                note=data.get('note', ''),
                issued_by=_actor_admin(request),
            )
        except (InventoryError, InventoryUnitError, InsufficientStockError) as exc:
            return _error_response(exc)
        return Response(
            KitchenUsageSerializer(usage).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryWastageCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryWastageCreate',
        summary='Record wastage',
        request=WastageSerializer,
        responses={201: WastageReadSerializer},
    )
    def post(self, request):
        serializer = WastageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = _get_item_or_404(data['item_public_id'])
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            wastage = record_wastage(
                item=item,
                quantity=data['quantity'],
                unit=data.get('unit'),
                reason=data['reason'],
                note=data.get('note', ''),
                recorded_by=_actor_admin(request),
            )
        except (InventoryError, InventoryUnitError, InsufficientStockError) as exc:
            return _error_response(exc)
        return Response(
            WastageReadSerializer(wastage).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryAdjustmentCreateView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryAdjustmentCreate',
        summary='Adjust stock',
        request=AdjustmentSerializer,
        responses={201: AdjustmentReadSerializer},
    )
    def post(self, request):
        serializer = AdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        item = _get_item_or_404(data['item_public_id'])
        if item is None:
            return Response(
                {
                    'success': False,
                    'message': 'Item not found.',
                    'errors': {},
                    'error_code': 'NOT_FOUND',
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            adjustment = adjust_stock(
                item=item,
                quantity_delta=data['quantity_delta'],
                unit=data.get('unit'),
                reason=data['reason'],
                note=data.get('note', ''),
                adjusted_by=_actor_admin(request),
            )
        except (InventoryError, InventoryUnitError, InsufficientStockError) as exc:
            return _error_response(exc)
        return Response(
            AdjustmentReadSerializer(adjustment).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryUsageHistoryView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryUsageHistory',
        summary='Kitchen usage history',
        responses={200: KitchenUsageSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_usages(
                InventoryKitchenUsage.objects.select_related(
                    'item', 'issued_by__user'
                ),
                request.query_params,
            )
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            KitchenUsageSerializer(page, many=True).data
        )


class InventoryReportView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryReport',
        summary='Allowlisted inventory report',
        parameters=[
            OpenApiParameter('date_from', str),
            OpenApiParameter('date_to', str),
        ],
        responses={200: OpenApiResponse(description='Report rows')},
    )
    def get(self, request, report_key):
        if report_key not in REPORT_KEYS:
            return Response(
                {
                    'success': False,
                    'message': f'Unsupported report key: {report_key}',
                    'errors': {},
                    'error_code': 'UNSUPPORTED_REPORT',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        rows = report_rows(report_key, request.query_params)
        return Response(
            {
                'report_key': report_key,
                'count': len(rows),
                'results': rows,
            }
        )


class InventoryAuditLogListView(APIView):
    permission_classes = [IsVerifiedAdmin]

    @extend_schema(
        tags=[INVENTORY_TAG],
        operation_id='inventoryAuditLogList',
        summary='Inventory audit logs',
        responses={200: InventoryAuditLogSerializer(many=True)},
    )
    def get(self, request):
        try:
            qs = filter_audit_logs(
                InventoryAuditLog.objects.select_related(
                    'actor_admin__user', 'item', 'purchase'
                ),
                request.query_params,
            )
        except ValueError as exc:
            return Response(
                {
                    'success': False,
                    'message': str(exc),
                    'errors': {},
                    'error_code': 'UNSUPPORTED_FILTER',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        paginator = InventoryPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            InventoryAuditLogSerializer(page, many=True).data
        )
