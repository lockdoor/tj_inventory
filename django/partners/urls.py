from django.urls import path
from partners.views.partner_views import PartnerListView

app_name = 'partners'

urlpatterns = [
    path('', PartnerListView.as_view(), name='partner-list'),
]
