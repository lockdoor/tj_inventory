from django.urls import path
from partners.views.partner_views import (
    PartnerListView, 
    PartnerDetailView, 
    PartnerCreateView, 
    PartnerUpdateView, 
    PartnerDeleteView,
    PartnerTrashListView,
    PartnerRestoreView
)

app_name = 'partners'

urlpatterns = [
    path('', PartnerListView.as_view(), name='partner-list'),
    path('trash/', PartnerTrashListView.as_view(), name='partner-trash'),
    path('add/', PartnerCreateView.as_view(), name='partner-create'),
    path('<str:code>/', PartnerDetailView.as_view(), name='partner-detail'),
    path('<str:code>/update/', PartnerUpdateView.as_view(), name='partner-update'),
    path('<str:code>/delete/', PartnerDeleteView.as_view(), name='partner-delete'),
    path('<str:code>/restore/', PartnerRestoreView.as_view(), name='partner-restore'),
]
