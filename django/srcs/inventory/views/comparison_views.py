from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from inventory.services.express_service import ExpressService

class StockComparisonListView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    View for comparing Django stock balances against external Express ERP balances.
    """
    template_name = 'inventory/stock_comparison.html'
    permission_required = 'inventory.view_stock'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = self.request.GET.get('company', None)
        
        context['company_id'] = company_id
        
        if company_id:
            context['comparison_data'] = ExpressService.get_comparison_data(company_id)
        else:
            context['comparison_data'] = []
            
        context['express_companies'] = ExpressService.get_companies() if ExpressService.is_alive() else []
        return context
