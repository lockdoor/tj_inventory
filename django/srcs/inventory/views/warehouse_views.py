from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView 
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from inventory.models import Warehouse
from inventory.forms.warehouse_form import WarehouseForm
from inventory.services.warehouse_service import WarehouseService

class WarehouseListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all active warehouses.
    """
    model = Warehouse
    template_name = 'inventory/warehouse_list.html'
    context_object_name = 'warehouses'
    permission_required = 'inventory.view_warehouse'
    raise_exception = True

    def get_queryset(self):
        return WarehouseService.get_queryable_queryset().order_by('code')

class WarehouseTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted warehouses (Trash).
    """
    model = Warehouse
    template_name = 'inventory/warehouse_trash_list.html'
    context_object_name = 'warehouses'
    permission_required = 'inventory.delete_warehouse'
    raise_exception = True

    def get_queryset(self):
        return WarehouseService.list_deleted()

class WarehouseDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single warehouse.
    Shows basic info, current stock balances, and recent movements.
    """
    model = Warehouse
    template_name = 'inventory/warehouse_detail.html'
    context_object_name = 'warehouse'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'inventory.view_warehouse'
    raise_exception = True

    def get_queryset(self):
        return WarehouseService.get_queryable_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch non-zero stock balances
        context['stocks'] = self.object.stocks.filter(balance__gt=0).select_related('item').order_by('item__sku', 'lot_number')
        # Fetch recent 10 movements
        context['recent_movements'] = self.object.movements.all().order_by('-date', '-created_at')[:10]
        return context

class WarehouseCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for creating a new Warehouse.
    """
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    permission_required = 'inventory.add_warehouse'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "New Warehouse"
        context['action_label'] = "Create Warehouse"
        return context

    def form_valid(self, form):
        try:
            warehouse = WarehouseService.create(
                name=form.cleaned_data['name'],
                code=form.cleaned_data['code'],
                user=self.request.user,
                note=form.cleaned_data['note'],
                status=form.cleaned_data['status']
            )
            messages.success(self.request, f"Warehouse '{warehouse.name}' created successfully!")
            return redirect('inventory:warehouse-list')
        except Exception as e:
            messages.error(self.request, f"Error creating warehouse: {str(e)}")
            return self.form_invalid(form)

class WarehouseUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    View for updating an existing Warehouse.
    """
    model = Warehouse
    form_class = WarehouseForm
    template_name = 'inventory/warehouse_form.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'inventory.change_warehouse'
    raise_exception = True

    def get_queryset(self):
        return WarehouseService.get_queryable_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Warehouse: {self.object.name}"
        context['action_label'] = "Update Warehouse"
        return context

    def form_valid(self, form):
        try:
            WarehouseService.update(
                self.object,
                user=self.request.user,
                name=form.cleaned_data['name'],
                code=form.cleaned_data['code'],
                note=form.cleaned_data['note'],
                status=form.cleaned_data['status']
            )
            messages.success(self.request, f"Warehouse '{self.object.name}' updated successfully!")
            return redirect('inventory:warehouse-list')
        except Exception as e:
            messages.error(self.request, f"Error updating warehouse: {str(e)}")
            return self.form_invalid(form)

class WarehouseDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting a Warehouse.
    """
    model = Warehouse
    template_name = 'inventory/warehouse_confirm_delete.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'inventory.delete_warehouse'
    success_url = reverse_lazy('inventory:warehouse-list')
    raise_exception = True

    def get_queryset(self):
        return WarehouseService.get_queryable_queryset()

    def form_valid(self, form):
        try:
            WarehouseService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Warehouse '{self.object.name}' moved to trash.")
            return redirect(self.success_url)
        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.get(self.request)
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)

class WarehouseRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Warehouse.
    """
    permission_required = 'inventory.delete_warehouse'
    raise_exception = True

    def post(self, request, code):
        warehouse = get_object_or_404(Warehouse, code=code, is_deleted=True)
        try:
            WarehouseService.restore(warehouse, user=request.user)
            messages.success(request, f"Warehouse '{warehouse.name}' restored successfully.")
            return redirect('inventory:warehouse-list')
        except Exception as e:
            messages.error(request, f"Error restoring warehouse: {str(e)}")
            return redirect('inventory:warehouse-trash')
