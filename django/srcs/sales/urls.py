from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('overview/', views.SalesOverviewView.as_view(), name='overview'),
    path('orders/', views.SalesOrderListView.as_view(), name='sales-order-list'),
    path('orders/create/', views.SalesOrderCreateView.as_view(), name='sales-order-create'),
]
