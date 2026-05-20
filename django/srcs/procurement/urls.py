from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('overview/', views.ProcurementOverviewView.as_view(), name='overview'),
    
    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchase-order-list'),
    path('purchase-orders/create/', views.PurchaseOrderCreateView.as_view(), name='purchase-order-create'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase-order-detail'),
    path('purchase-orders/<int:pk>/update/', views.PurchaseOrderUpdateView.as_view(), name='purchase-order-update'),
    path('purchase-orders/<int:pk>/submit/', views.PurchaseOrderSubmitView.as_view(), name='purchase-order-submit'),
    path('purchase-orders/<int:pk>/revert/', views.PurchaseOrderRevertView.as_view(), name='purchase-order-revert'),
    path('purchase-orders/<int:pk>/delete/', views.PurchaseOrderDeleteView.as_view(), name='purchase-order-delete'),
    
    # PO Attachments
    path('purchase-orders/<int:pk>/attachment/upload/', views.PurchaseOrderAttachmentUploadView.as_view(), name='purchase-order-attachment-upload'),
    path('purchase-orders/attachment/<int:pk>/delete/', views.PurchaseOrderAttachmentDeleteView.as_view(), name='purchase-order-attachment-delete'),

    path('purchase-orders/<int:pk>/items-api/', views.PurchaseOrderItemsAPIView.as_view(), name='purchase-order-items-api'),

    # Arrivals
    path('arrivals/', views.ArrivalListView.as_view(), name='arrival-list'),
    path('arrivals/create/', views.ArrivalCreateView.as_view(), name='arrival-create'),
    path('arrivals/<int:pk>/', views.ArrivalDetailView.as_view(), name='arrival-detail'),
    path('arrivals/<int:pk>/update/', views.ArrivalUpdateView.as_view(), name='arrival-update'),
    path('arrivals/from-po/<int:po_pk>/', views.ArrivalFromPOView.as_view(), name='arrival-from-po'),
    path('arrivals/<int:pk>/receive/', views.ArrivalReceiveActionView.as_view(), name='arrival-receive'),
    path('arrivals/<int:pk>/cancel-receive/', views.ArrivalCancelReceiveActionView.as_view(), name='arrival-cancel-receive'),
    path('arrivals/<int:pk>/delete/', views.ArrivalDeleteActionView.as_view(), name='arrival-delete'),

    # Arrival Attachments
    path('arrivals/<int:pk>/attachment/upload/', views.ArrivalAttachmentUploadView.as_view(), name='arrival-attachment-upload'),
    path('arrivals/attachment/<int:pk>/delete/', views.ArrivalAttachmentDeleteView.as_view(), name='arrival-attachment-delete'),
]
