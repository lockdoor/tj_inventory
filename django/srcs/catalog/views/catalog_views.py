from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from catalog.services import CategoryService, ItemService

class CatalogOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Overview dashboard for the Catalog module.
    Displays summary statistics and serves as the primary navigation hub.
    """
    template_name = 'catalog/overview.html'
    permission_required = 'catalog.view_category'  # Base permission to view catalog

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Aggregate stats from services
        context['category_count'] = CategoryService.get_active_queryset().count()
        context['item_count'] = ItemService.get_active_queryset().count()
        
        from partners.models import Partner
        context['partner_count'] = Partner.objects.filter(is_deleted=False).count()
        
        return context
