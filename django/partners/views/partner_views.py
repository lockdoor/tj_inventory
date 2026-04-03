from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from partners.models import Partner
from partners.services.partner_service import PartnerService

class PartnerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all partners.
    """
    model = Partner
    template_name = 'partners/partner_list.html'
    context_object_name = 'partners'
    permission_required = 'partners.view_partner'
    raise_exception = True

    def get_queryset(self):
        """
        Ensures we only list active (non-deleted) partners.
        """
        queryset = PartnerService.get_active_queryset()
        
        # Simple optional filter for supplier/customer
        role = self.request.GET.get('role')
        if role == 'supplier':
            queryset = queryset.filter(is_supplier=True)
        elif role == 'customer':
            queryset = queryset.filter(is_customer=True)
            
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_role'] = self.request.GET.get('role', 'all')
        return context
