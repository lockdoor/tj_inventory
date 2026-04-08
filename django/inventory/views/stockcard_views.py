from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from inventory.models import StockCard

class StockCardListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Chronological ledger of all inventory transactions.
    """
    model = StockCard
    template_name = 'inventory/stockcard_list.html'
    context_object_name = 'stockcards'
    permission_required = 'inventory.view_stockcard'
    raise_exception = True
    paginate_by = 15

    def get_queryset(self):
        """Optimize with select_related for performance."""
        return StockCard.objects.select_related(
            'item', 
            'warehouse', 
            'movement_item__movement'
        ).all().order_by('-created_at')

class StockCardDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Deep-dive view for specific audit entries.
    """
    model = StockCard
    template_name = 'inventory/stockcard_detail.html'
    context_object_name = 'stockcard'
    permission_required = 'inventory.view_stockcard'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass snapshot helpers if needed
        return context
