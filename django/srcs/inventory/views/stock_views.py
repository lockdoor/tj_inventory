from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from inventory.services.stock_service import StockService

class StockBalanceListView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Hierarchical view of current stock balances.
    Warehouse -> Item -> Lot
    """
    template_name = 'inventory/stock_list.html'
    permission_required = 'inventory.view_stock'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch structured data from service
        context['hierarchy'] = StockService.get_hierarchical_stock_balances()
        
        # Add express companies for the balance comparison feature
        from inventory.services.express_service import ExpressService
        context['express_companies'] = ExpressService.get_companies()
        
        return context
