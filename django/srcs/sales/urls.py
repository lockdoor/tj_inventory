from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('overview/', views.SalesOverviewView.as_view(), name='overview'),
    path('orders/', views.SalesOrderListView.as_view(), name='sales-order-list'),
    path('orders/create/', views.SalesOrderCreateView.as_view(), name='sales-order-create'),
    path('orders/<int:pk>/', views.SalesOrderDetailView.as_view(), name='sales-order-detail'),
    path('orders/<int:pk>/edit/', views.SalesOrderUpdateView.as_view(), name='sales-order-edit'),
    path('orders/<int:pk>/refresh-allocations/', views.SalesOrderRefreshAllocationView.as_view(), name='sales-order-refresh-allocations'),
    path('orders/<int:pk>/release/', views.SalesOrderReleaseToWarehouseView.as_view(), name='sales-order-release'),
    path('orders/<int:pk>/confirm/', views.SalesOrderConfirmView.as_view(), name='sales-order-confirm'),
    path('orders/<int:pk>/revert-to-draft/', views.SalesOrderRevertToDraftView.as_view(), name='sales-order-revert-to-draft'),
    path('orders/items/<int:item_pk>/allocate/', views.SalesOrderItemAllocateView.as_view(), name='sales-order-item-allocate'),
    path('orders/items/<int:item_pk>/reset-allocation/', views.SalesOrderItemResetAllocationView.as_view(), name='sales-order-item-reset-allocation'),
    path('orders/<int:pk>/attachment/upload/', views.SalesOrderAttachmentUploadView.as_view(), name='sales-order-attachment-upload'),
    path('orders/attachment/<int:pk>/delete/', views.SalesOrderAttachmentDeleteView.as_view(), name='sales-order-attachment-delete'),
]

