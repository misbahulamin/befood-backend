from django.urls import path

from inventory.api.views import (
    InventoryAdjustmentCreateView,
    InventoryAuditLogListView,
    InventoryDashboardView,
    InventoryItemDetailView,
    InventoryItemListCreateView,
    InventoryItemMovementsView,
    InventoryPurchaseCancelView,
    InventoryPurchaseConfirmView,
    InventoryPurchaseDetailView,
    InventoryPurchaseInvoiceView,
    InventoryPurchaseListCreateView,
    InventoryReportView,
    InventoryStockIssueView,
    InventoryUsageHistoryView,
    InventoryWastageCreateView,
)

app_name = 'web_inventory'

urlpatterns = [
    path('dashboard/', InventoryDashboardView.as_view(), name='dashboard'),
    path('items/', InventoryItemListCreateView.as_view(), name='items'),
    path('items/<uuid:public_id>/', InventoryItemDetailView.as_view(), name='item-detail'),
    path(
        'items/<uuid:public_id>/movements/',
        InventoryItemMovementsView.as_view(),
        name='item-movements',
    ),
    path('purchases/', InventoryPurchaseListCreateView.as_view(), name='purchases'),
    path(
        'purchase-history/',
        InventoryPurchaseListCreateView.as_view(),
        name='purchase-history',
    ),
    path(
        'purchases/<uuid:public_id>/',
        InventoryPurchaseDetailView.as_view(),
        name='purchase-detail',
    ),
    path(
        'purchases/<uuid:public_id>/confirm/',
        InventoryPurchaseConfirmView.as_view(),
        name='purchase-confirm',
    ),
    path(
        'purchases/<uuid:public_id>/cancel/',
        InventoryPurchaseCancelView.as_view(),
        name='purchase-cancel',
    ),
    path(
        'purchases/<uuid:public_id>/invoice/',
        InventoryPurchaseInvoiceView.as_view(),
        name='purchase-invoice',
    ),
    path('stock-issues/', InventoryStockIssueView.as_view(), name='stock-issues'),
    path('wastages/', InventoryWastageCreateView.as_view(), name='wastages'),
    path('adjustments/', InventoryAdjustmentCreateView.as_view(), name='adjustments'),
    path('usage-history/', InventoryUsageHistoryView.as_view(), name='usage-history'),
    path('reports/<str:report_key>/', InventoryReportView.as_view(), name='reports'),
    path('audit-logs/', InventoryAuditLogListView.as_view(), name='audit-logs'),
]
