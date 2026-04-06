from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView
from inventory.models import InventoryMovement

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
        return InventoryMovement.objects.select_related('warehouse', 'partner').all()
