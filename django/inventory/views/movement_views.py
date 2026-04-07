from django.db import transaction
from django.shortcuts import redirect
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from inventory.models import InventoryMovement, InventoryMovementItem, StockCard
from inventory.forms import MovementCreateForm, MovementItemFormSet

class MovementCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Unified creation engine for Inventory Movements.
    Handles Header + Inline Item FormSet within a single atomic transaction.
    """
    model = InventoryMovement
    form_class = MovementCreateForm
    template_name = 'inventory/movement_create.html'
    permission_required = 'inventory.add_inventorymovement'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = MovementItemFormSet(self.request.POST)
        else:
            context['items'] = MovementItemFormSet()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            with transaction.atomic():
                form.instance.created_by = self.request.user
                self.object = form.save()
                items.instance = self.object
                items.save()
            return redirect('inventory:movement-detail', document_no=self.object.document_no)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Ensure formset errors are passed back to the context."""
        return self.render_to_response(self.get_context_data(form=form))

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
