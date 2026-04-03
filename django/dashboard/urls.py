from django.urls import path
from .views.dashboard_views import DashboardView

app_name = 'dashboard'

urlpatterns = [
    path('', DashboardView.as_view(), name='overview'),
]
