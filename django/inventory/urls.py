from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('overview/', views.InventoryOverviewView.as_view(), name='overview'),

    # Warehouses
    path('warehouses/', views.WarehouseListView.as_view(), name='warehouse-list'),
    path('warehouses/trash/', views.WarehouseTrashListView.as_view(), name='warehouse-trash'),
    path('warehouses/create/', views.WarehouseCreateView.as_view(), name='warehouse-create'),
    path('warehouses/<str:code>/', views.WarehouseDetailView.as_view(), name='warehouse-detail'),
    path('warehouses/<str:code>/update/', views.WarehouseUpdateView.as_view(), name='warehouse-update'),
    path('warehouses/<str:code>/delete/', views.WarehouseDeleteView.as_view(), name='warehouse-delete'),
    path('warehouses/<str:code>/restore/', views.WarehouseRestoreView.as_view(), name='warehouse-restore'),

    # Movements
    path('movements/', views.MovementListView.as_view(), name='movement-list'),
    path('movements/create/', views.MovementCreateView.as_view(), name='movement-create'),
    path('movements/<str:document_no>/', views.MovementDetailView.as_view(), name='movement-detail'),
    path('movements/<str:document_no>/complete/', views.MovementCompleteView.as_view(), name='movement-complete'),
    path('movements/<str:document_no>/revert/', views.MovementRevertView.as_view(), name='movement-revert'),
    path('movements/<str:document_no>/delete/', views.MovementDeleteView.as_view(), name='movement-delete'),
    
    # Stock Ledger
    path('ledger/', views.StockCardListView.as_view(), name='stockcard-list'),
    path('ledger/<int:pk>/', views.StockCardDetailView.as_view(), name='stockcard-detail'),

    # Balances
    path('balances/', views.StockBalanceListView.as_view(), name='stock-balance-list'),
]
