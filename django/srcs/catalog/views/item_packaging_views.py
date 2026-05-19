from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.views.generic import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from catalog.models import Item, ItemPackaging
from catalog.services.item_packaging_service import ItemPackagingService
from catalog.forms import ItemPackagingForm


from django.core.exceptions import ValidationError

class ItemPackagingCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Form view for creating a new ItemPackaging unit for a specific Item.
    """
    model = ItemPackaging
    form_class = ItemPackagingForm
    template_name = 'catalog/item_packaging_form.html'
    permission_required = 'catalog.add_itempackaging'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = get_object_or_404(Item, sku=self.kwargs['sku'], is_deleted=False)
        context['title'] = f"Add Packaging for {item.name}"
        context['item'] = item
        context['action_label'] = "Add Packaging"
        return context

    def form_valid(self, form):
        item = get_object_or_404(Item, sku=self.kwargs['sku'], is_deleted=False)
        data = form.cleaned_data
        try:
            ItemPackagingService.create(
                item=item,
                name=data['name'],
                quantity=data['quantity'],
                barcode=data['barcode'],
                note=data['note'],
                status=data['status'],
                user=self.request.user
            )
            messages.success(self.request, f"Packaging '{data['name']}' added successfully to {item.sku}.")
            return redirect('catalog:item-detail', sku=item.sku)
        except (ValueError, ValidationError) as e:
            error_msg = str(e)
            if hasattr(e, 'messages'):
                error_msg = ", ".join(e.messages)
            form.add_error(None, error_msg)
            return self.form_invalid(form)


class ItemPackagingUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Form view for updating an existing ItemPackaging unit.
    """
    model = ItemPackaging
    form_class = ItemPackagingForm
    template_name = 'catalog/item_packaging_form.html'
    permission_required = 'catalog.change_itempackaging'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Packaging: {self.object.name}"
        context['item'] = self.object.item
        context['action_label'] = "Save Changes"
        return context

    def form_valid(self, form):
        try:
            self.object = ItemPackagingService.update(
                self.object,
                user=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Packaging '{self.object.name}' updated successfully.")
            return redirect('catalog:item-detail', sku=self.object.item.sku)
        except (ValueError, ValidationError) as e:
            error_msg = str(e)
            if hasattr(e, 'messages'):
                error_msg = ", ".join(e.messages)
            form.add_error(None, error_msg)
            return self.form_invalid(form)


class ItemPackagingDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting an ItemPackaging unit.
    """
    model = ItemPackaging
    template_name = 'catalog/item_packaging_confirm_delete.html'
    permission_required = 'catalog.delete_itempackaging'
    raise_exception = True

    def form_valid(self, form):
        item = self.object.item
        name = self.object.name
        ItemPackagingService.delete(self.object, user=self.request.user)
        messages.success(self.request, f"Packaging '{name}' deleted successfully from {item.sku}.")
        return redirect('catalog:item-detail', sku=item.sku)


from django.http import JsonResponse
from django.views import View

class ItemPackagingsAPIView(LoginRequiredMixin, View):
    """
    Returns JSON list of active packagings for a given Item ID.
    """
    def get(self, request, item_id):
        item = get_object_or_404(Item, id=item_id, is_deleted=False)
        packagings = item.packagings.filter(status=ItemPackaging.Status.ACTIVE, is_deleted=False).order_by('quantity')
        data = [
            {
                'id': p.id,
                'name': p.name,
                'quantity': p.quantity,
                'display': f"{p.name} ({p.quantity} pcs)"
            }
            for p in packagings
        ]
        return JsonResponse({'packagings': data, 'base_unit': item.unit})

