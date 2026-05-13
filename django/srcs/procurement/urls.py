from django.urls import path
from . import views

app_name = 'procurement'

urlpatterns = [
    path('purchase-orders/', views.PurchaseOrderListView.as_view(), name='purchase-order-list'),
    path('purchase-orders/create/', views.PurchaseOrderCreateView.as_view(), name='purchase-order-create'),
    path('purchase-orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='purchase-order-detail'),
    path('purchase-orders/<int:pk>/update/', views.PurchaseOrderUpdateView.as_view(), name='purchase-order-update'),
    path('purchase-orders/<int:pk>/submit/', views.PurchaseOrderSubmitView.as_view(), name='purchase-order-submit'),
    path('purchase-orders/<int:pk>/revert/', views.PurchaseOrderRevertView.as_view(), name='purchase-order-revert'),
    
    # PO Attachments
    path('purchase-orders/<int:pk>/attachment/upload/', views.PurchaseOrderAttachmentUploadView.as_view(), name='purchase-order-attachment-upload'),
    path('purchase-orders/attachment/<int:pk>/delete/', views.PurchaseOrderAttachmentDeleteView.as_view(), name='purchase-order-attachment-delete'),

    # Arrival Attachments
    path('arrivals/<int:pk>/attachment/upload/', views.ArrivalAttachmentUploadView.as_view(), name='arrival-attachment-upload'),
    path('arrivals/attachment/<int:pk>/delete/', views.ArrivalAttachmentDeleteView.as_view(), name='arrival-attachment-delete'),
]
