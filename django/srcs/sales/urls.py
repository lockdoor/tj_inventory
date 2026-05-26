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
    path('orders/items/<int:item_pk>/allocate/', views.SalesOrderItemAllocateView.as_view(), name='sales-order-item-allocate'),
    path('orders/items/<int:item_pk>/reset-allocation/', views.SalesOrderItemResetAllocationView.as_view(), name='sales-order-item-reset-allocation'),
]

