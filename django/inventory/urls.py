from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('overview/', views.InventoryOverviewView.as_view(), name='overview'),
]
