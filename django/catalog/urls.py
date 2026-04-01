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

app_name = 'catalog'

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/trash/', CategoryTrashListView.as_view(), name='category-trash'),
    path('categories/create/', CategoryCreateView.as_view(), name='category-create'),
    path('categories/<int:pk>/', CategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/update/', CategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', CategoryDeleteView.as_view(), name='category-delete'),
    path('categories/<int:pk>/restore/', CategoryRestoreView.as_view(), name='category-restore'),
]
