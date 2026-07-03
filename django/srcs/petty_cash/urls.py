from django.urls import path
from petty_cash.views import (
    PettyCashOverviewView,
    PettyCashCategoryListView,
    PettyCashCategoryCreateView,
    PettyCashCategoryDetailView,
    PettyCashCategoryUpdateView,
    PettyCashCategoryDeleteView,
    PettyCashCategoryTrashListView,
    PettyCashCategoryRestoreView,
    PettyCashCategorySyncView
)

app_name = 'petty_cash'

urlpatterns = [
    path('', PettyCashOverviewView.as_view(), name='overview'),
    path('categories/', PettyCashCategoryListView.as_view(), name='category-list'),
    path('categories/create/', PettyCashCategoryCreateView.as_view(), name='category-create'),
    path('categories/trash/', PettyCashCategoryTrashListView.as_view(), name='category-trash'),
    path('categories/sync/<int:company_id>/', PettyCashCategorySyncView.as_view(), name='category-sync'),
    path('categories/<int:pk>/', PettyCashCategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/update/', PettyCashCategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', PettyCashCategoryDeleteView.as_view(), name='category-delete'),
    path('categories/<int:pk>/restore/', PettyCashCategoryRestoreView.as_view(), name='category-restore'),
]
