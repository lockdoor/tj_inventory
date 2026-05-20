from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class ProcurementOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Main overview for the Procurement module.
    Displays cards for Purchase Orders and Arrival Schedules management.
    """
    template_name = 'procurement/overview.html'
    permission_required = 'procurement.view_purchaseorder'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Procurement Overview"
        return context
