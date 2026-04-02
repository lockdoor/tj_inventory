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
from catalog.views.item_views import ItemListView, ItemCreateView, ItemUpdateView
from catalog.views.catalog_views import CatalogOverviewView

app_name = 'catalog'

urlpatterns = [
    # General
    path('', CatalogOverviewView.as_view(), name='catalog-overview'),

    # Categories
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/trash/', CategoryTrashListView.as_view(), name='category-trash'),
    path('categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/update/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category-delete'),
    path('categories/<int:pk>/restore/', CategoryRestoreView.as_view(), name='category-restore'),

    # Items
    path('items/', ItemListView.as_view(), name='item-list'),
    path('items/create/', ItemCreateView.as_view(), name='item-create'),
    path('items/<int:pk>/update/', ItemUpdateView.as_view(), name='item-update'),
]
