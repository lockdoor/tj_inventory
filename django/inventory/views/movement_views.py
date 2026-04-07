from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, DetailView
from inventory.models import InventoryMovement, InventoryMovementItem, StockCard

class MovementListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Paginated ledger of all inventory movements.
    """
    model = InventoryMovement
    template_name = 'inventory/movement_list.html'
    context_object_name = 'movements'
    permission_required = 'inventory.view_inventorymovement'
    raise_exception = True
    paginate_by = 10

    def get_queryset(self):
        """Optimize with select_related for performance."""
        return InventoryMovement.objects.select_related('warehouse', 'partner').all().order_by('-date', '-created_at')

class MovementDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed transaction view with item lists and audit trackers.
    """
    model = InventoryMovement
    template_name = 'inventory/movement_detail.html'
    context_object_name = 'movement'
    permission_required = 'inventory.view_inventorymovement'
    raise_exception = True
    slug_field = 'document_no'
    slug_url_kwarg = 'document_no'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch related items with SKU/Name pre-fetched
        context['items'] = self.object.items.select_related('item').all()
        
        # Fetch audit trail if the movement is completed
        if self.object.status == 'completed':
            context['audit_trail'] = StockCard.objects.filter(
                movement_item__movement=self.object
            ).select_related('item', 'warehouse')
            
        return context
