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
    PettyCashCategorySyncView,
    PettyCashAccountListView,
    PettyCashAccountCreateView,
    PettyCashAccountDetailView,
    PettyCashAccountUpdateView,
    PettyCashAccountDeleteView,
    PettyCashAccountTrashListView,
    PettyCashAccountRestoreView,
    PettyCashPaymentListView,
    PettyCashPaymentDetailView,
    PettyCashPaymentCreateView,
    PettyCashPaymentUpdateView,
    PettyCashPaymentCancelView,
    PettyCashPaymentTrashListView,
    PettyCashPaymentSummaryView
)

app_name = 'petty_cash'

urlpatterns = [
    path('', PettyCashOverviewView.as_view(), name='overview'),
    
    # Categories
    path('categories/', PettyCashCategoryListView.as_view(), name='category-list'),
    path('categories/create/', PettyCashCategoryCreateView.as_view(), name='category-create'),
    path('categories/trash/', PettyCashCategoryTrashListView.as_view(), name='category-trash'),
    path('categories/sync/<int:company_id>/', PettyCashCategorySyncView.as_view(), name='category-sync'),
    path('categories/<int:pk>/', PettyCashCategoryDetailView.as_view(), name='category-detail'),
    path('categories/<int:pk>/update/', PettyCashCategoryUpdateView.as_view(), name='category-update'),
    path('categories/<int:pk>/delete/', PettyCashCategoryDeleteView.as_view(), name='category-delete'),
    path('categories/<int:pk>/restore/', PettyCashCategoryRestoreView.as_view(), name='category-restore'),

    # Accounts
    path('accounts/', PettyCashAccountListView.as_view(), name='account-list'),
    path('accounts/create/', PettyCashAccountCreateView.as_view(), name='account-create'),
    path('accounts/trash/', PettyCashAccountTrashListView.as_view(), name='account-trash'),
    path('accounts/<int:pk>/', PettyCashAccountDetailView.as_view(), name='account-detail'),
    path('accounts/<int:pk>/update/', PettyCashAccountUpdateView.as_view(), name='account-update'),
    path('accounts/<int:pk>/delete/', PettyCashAccountDeleteView.as_view(), name='account-delete'),
    path('accounts/<int:pk>/restore/', PettyCashAccountRestoreView.as_view(), name='account-restore'),

    # Payments
    path('payments/account/<str:account_code>/', PettyCashPaymentListView.as_view(), name='payment-list'),
    path('payments/account/<str:account_code>/create/', PettyCashPaymentCreateView.as_view(), name='payment-create'),
    path('payments/account/<str:account_code>/trash/', PettyCashPaymentTrashListView.as_view(), name='payment-trash'),
    path('payments/account/<str:account_code>/summary/', PettyCashPaymentSummaryView.as_view(), name='payment-summary'),
    path('payments/<int:pk>/', PettyCashPaymentDetailView.as_view(), name='payment-detail'),
    path('payments/<int:pk>/update/', PettyCashPaymentUpdateView.as_view(), name='payment-update'),
    path('payments/<int:pk>/cancel/', PettyCashPaymentCancelView.as_view(), name='payment-cancel'),
]
