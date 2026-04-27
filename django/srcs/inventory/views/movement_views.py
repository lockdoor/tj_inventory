from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.contrib import messages
from inventory.models import InventoryMovement, InventoryMovementItem, StockCard
from inventory.forms import MovementCreateForm, MovementItemFormSet
from inventory.services.movement_service import MovementService
class MovementCompleteView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View to trigger document fulfillment."""
    model = InventoryMovement
    permission_required = 'inventory.add_inventorymovement'
    slug_field = 'document_no'
    slug_url_kwarg = 'document_no'

    def post(self, request, *args, **kwargs):
        movement = self.get_object()
        try:
            MovementService.complete_movement(movement, user=request.user)
            messages.success(request, f"Document {movement.document_no} completed successfully.")
        except Exception as e:
            messages.error(request, f"Error completing document: {str(e)}")
        return redirect('inventory:movement-detail', document_no=movement.document_no)

class MovementRevertView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View to trigger fulfillment reversal."""
    model = InventoryMovement
    permission_required = 'inventory.add_inventorymovement' # Requires high level permission
    slug_field = 'document_no'
    slug_url_kwarg = 'document_no'

    def post(self, request, *args, **kwargs):
        movement = self.get_object()
        try:
            MovementService.revert_to_draft(movement, user=request.user)
            messages.warning(request, f"Document {movement.document_no} reverted to Draft. Stock ledger updated.")
        except Exception as e:
            messages.error(request, f"Error reverting document: {str(e)}")
        return redirect('inventory:movement-detail', document_no=movement.document_no)

class MovementDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """View to trigger document discard (deletion)."""
    model = InventoryMovement
    permission_required = 'inventory.delete_inventorymovement'
    slug_field = 'document_no'
    slug_url_kwarg = 'document_no'

    def post(self, request, *args, **kwargs):
        movement = self.get_object()
        try:
            doc_no = movement.document_no
            MovementService.delete_draft(movement, user=request.user)
            messages.info(request, f"Document {doc_no} has been discarded.")
            return redirect('inventory:movement-list')
        except Exception as e:
            messages.error(request, f"Error discarding document: {str(e)}")
            return redirect('inventory:movement-detail', document_no=movement.document_no)

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
        form = kwargs.get('form', self.get_form())
        
        # Prepare kwargs for the formset forms
        formset_kwargs = {}
        if form.is_bound:
            # Try to get warehouse and type from bound form
            warehouse_id = form.data.get('warehouse')
            m_type = form.data.get('type')
            if warehouse_id:
                try:
                    from inventory.models import Warehouse
                    formset_kwargs['warehouse'] = Warehouse.objects.get(id=warehouse_id)
                except: pass
            formset_kwargs['movement_type'] = m_type

        if self.request.POST:
            context['items'] = MovementItemFormSet(
                self.request.POST, 
                form_kwargs=formset_kwargs
            )
        else:
            context['items'] = MovementItemFormSet()
        return context

    def form_valid(self, form):
        # Re-fetch context to ensure formset has access to bound header data
        context = self.get_context_data(form=form)
        items = context['items']
        
        # Link items to the unsaved header instance for Django's internal logic
        items.instance = form.instance
        
        if items.is_valid():
            with transaction.atomic():
                form.instance.created_by = self.request.user
                self.object = form.save()
                items.save()
            return redirect('inventory:movement-detail', document_no=self.object.document_no)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Ensure formset errors are passed back to the context."""
        return self.render_to_response(self.get_context_data(form=form))

class MovementUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Update engine for Inventory Movements.
    Allows editing Draft documents including their line items.
    """
    model = InventoryMovement
    form_class = MovementCreateForm
    template_name = 'inventory/movement_create.html' # Reuse the same template
    permission_required = 'inventory.change_inventorymovement'
    slug_field = 'document_no'
    slug_url_kwarg = 'document_no'
    raise_exception = True

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status != InventoryMovement.Status.DRAFT:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Only Draft documents can be updated.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = kwargs.get('form', self.get_form())
        
        # Prepare kwargs for the formset forms
        formset_kwargs = {}
        # For update, we use the instance data
        warehouse = self.object.warehouse
        m_type = self.object.type
        
        if form.is_bound:
            # If form is bound (validation failed), use the submitted data
            warehouse_id = form.data.get('warehouse')
            m_type = form.data.get('type')
            if warehouse_id:
                try:
                    from inventory.models import Warehouse
                    warehouse = Warehouse.objects.get(id=warehouse_id)
                except: pass

        formset_kwargs['warehouse'] = warehouse
        formset_kwargs['movement_type'] = m_type

        if self.request.POST:
            context['items'] = MovementItemFormSet(
                self.request.POST, 
                instance=self.object,
                form_kwargs=formset_kwargs
            )
        else:
            context['items'] = MovementItemFormSet(
                instance=self.object,
                form_kwargs=formset_kwargs
            )
        context['is_update'] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        items = context['items']
        
        if items.is_valid():
            with transaction.atomic():
                form.instance.updated_by = self.request.user
                self.object = form.save()
                items.save()
            messages.success(self.request, f"Document {self.object.document_no} updated successfully.")
            return redirect('inventory:movement-detail', document_no=self.object.document_no)
        else:
            return self.form_invalid(form)

    def form_invalid(self, form):
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
        """Select non soft delete"""
        """Optimize with select_related for performance."""
        return InventoryMovement.objects.select_related('warehouse', 'partner').filter(is_deleted=False).order_by('-date', '-created_at')
        #return InventoryMovement.objects.select_related('warehouse', 'partner').all().order_by('-date', '-created_at')

class MovementTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted movements (Trash).
    """
    model = InventoryMovement
    template_name = 'inventory/movement_trash_list.html'
    context_object_name = 'movements'
    permission_required = 'inventory.delete_inventorymovement'
    raise_exception = True
    paginate_by = 10

    def get_queryset(self):
        return MovementService.list_deleted()

class MovementRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted movement.
    """
    permission_required = 'inventory.delete_inventorymovement'
    raise_exception = True

    def post(self, request, document_no):
        movement = get_object_or_404(InventoryMovement, document_no=document_no, is_deleted=True)
        try:
            MovementService.restore(movement, user=request.user)
            messages.success(request, f"Document '{movement.document_no}' restored successfully.")
            return redirect('inventory:movement-list')
        except Exception as e:
            messages.error(request, f"Error restoring document: {str(e)}")
            return redirect('inventory:movement-trash')

class MovementHardDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for permanently deleting a movement document.
    Requires the user to confirm via document number verification in UI.
    """
    permission_required = 'inventory.delete_inventorymovement'
    raise_exception = True

    def post(self, request, document_no):
        movement = get_object_or_404(InventoryMovement, document_no=document_no, is_deleted=True)
        try:
            doc_no = movement.document_no
            # Perform hard delete
            movement.hard_delete()
            messages.success(request, f"Document '{doc_no}' has been permanently deleted.")
        except Exception as e:
            messages.error(request, f"Error during permanent deletion: {str(e)}")
        return redirect('inventory:movement-trash')

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

        # Fetch attachments (excluding soft-deleted ones)
        context['attachments'] = self.object.attachments.filter(is_deleted=False)
        # Add empty form for new upload
        from inventory.forms.attachment_form import MovementAttachmentForm
        context['attachment_form'] = MovementAttachmentForm()
            
        return context
