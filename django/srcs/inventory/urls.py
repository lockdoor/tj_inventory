from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # API endpoints
    path('api/lots/', views.AvailableLotsAPIView.as_view(), name='api-lots'),

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
    path('movements/trash/', views.MovementTrashListView.as_view(), name='movement-trash'),
    path('movements/create/', views.MovementCreateView.as_view(), name='movement-create'),
    path('movements/<int:pk>/restore/', views.MovementRestoreView.as_view(), name='movement-restore'),
    path('movements/<int:pk>/update/', views.MovementUpdateView.as_view(), name='movement-update'),
    path('movements/<int:pk>/', views.MovementDetailView.as_view(), name='movement-detail'),
    path('movements/<int:pk>/complete/', views.MovementCompleteView.as_view(), name='movement-complete'),
    path('movements/<int:pk>/revert/', views.MovementRevertView.as_view(), name='movement-revert'),
    path('movements/<int:pk>/delete/', views.MovementDeleteView.as_view(), name='movement-delete'),
    path('movements/<int:pk>/hard-delete/', views.MovementHardDeleteView.as_view(), name='movement-hard-delete'),
    
    # Movement Attachments
    path('movements/<int:pk>/attach/', views.MovementAttachmentUploadView.as_view(), name='movement-attachment-upload'),
    path('attachments/<int:pk>/delete/', views.MovementAttachmentDeleteView.as_view(), name='movement-attachment-delete'),
    
    # Stock Ledger
    path('ledger/', views.StockCardListView.as_view(), name='stockcard-list'),
    path('ledger/<int:pk>/', views.StockCardDetailView.as_view(), name='stockcard-detail'),

    # Balances
    path('balances/', views.StockBalanceListView.as_view(), name='stock-balance-list'),
    path('compare-express/', views.StockComparisonListView.as_view(), name='stock-comparison'),
]
