from django.urls import path
from catalog.views.category_views import (
    CategoryCreateView, 
    CategoryListView, 
    CategoryDetailView,
    CategoryUpdateView,
    CategoryDeleteView,
    CategoryTrashListView,
    CategoryRestoreView
)
from catalog.views.item_views import (
    ItemListView, 
    ItemCreateView, 
    ItemUpdateView, 
    ItemDetailView,
    ItemTrashListView,
    ItemDeleteView,
    ItemRestoreView
)
from catalog.views.catalog_views import CatalogOverviewView

app_name = 'catalog'

urlpatterns = [
    # General
    path('', CatalogOverviewView.as_view(), name='catalog-overview'),

    # Categories
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/trash/', CategoryTrashListView.as_view(), name='category-trash'),
    path('categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('categories/<str:code>/', CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<str:code>/update/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<str:code>/delete/', CategoryDeleteView.as_view(), name='category-delete'),
    path('categories/<str:code>/restore/', CategoryRestoreView.as_view(), name='category-restore'),

    # Items
    path('items/', ItemListView.as_view(), name='item-list'),
    path('items/trash/', ItemTrashListView.as_view(), name='item-trash'),
    path('items/create/', ItemCreateView.as_view(), name='item-create'),
    path('items/<str:sku>/', ItemDetailView.as_view(), name='item-detail'),
    path('items/<str:sku>/update/', ItemUpdateView.as_view(), name='item-update'),
    path('items/<str:sku>/delete/', ItemDeleteView.as_view(), name='item-delete'),
    path('items/<str:sku>/restore/', ItemRestoreView.as_view(), name='item-restore'),
]
