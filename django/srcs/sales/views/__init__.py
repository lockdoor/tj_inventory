from .overview_views import SalesOverviewView
from .sales_order_views import (
    SalesOrderListView,
    SalesOrderCreateView,
    SalesOrderUpdateView,
    SalesOrderDetailView,
    SalesOrderRefreshAllocationView,
    SalesOrderItemAllocateView,
    SalesOrderItemResetAllocationView,
    SalesOrderReleaseToWarehouseView,
    SalesOrderConfirmView,
    SalesOrderRevertToDraftView,
    SalesOrderItemDeleteView,
)
from .attachment_views import (
    SalesOrderAttachmentUploadView,
    SalesOrderAttachmentDeleteView,
)

