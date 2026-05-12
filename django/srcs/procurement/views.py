from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import PurchaseOrder

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'procurement/purchase_order_list.html'
    context_object_name = 'purchase_orders'
    permission_required = 'procurement.view_purchaseorder'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False).select_related('partner')
