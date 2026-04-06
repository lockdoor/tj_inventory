from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class InventoryOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Main overview for the Inventory module.
    Displays cards for Warehouse, Movement, Stock, and StockCard management.
    """
    template_name = 'inventory/overview.html'
    permission_required = 'inventory.view_warehouse'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Inventory Overview"
        return context
