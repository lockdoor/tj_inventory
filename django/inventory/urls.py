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
]
