from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from catalog.models import Item
from catalog.services.item_service import ItemService
from catalog.forms import ItemForm
from django.urls import reverse_lazy

class ItemListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all items in the catalog.
    Accessible to all users with 'view_item' permission.
    """
    model = Item
    template_name = 'catalog/item_list.html'
    context_object_name = 'items'
    permission_required = 'catalog.view_item'
    raise_exception = True

    def get_queryset(self):
        """
        Return active items with optimized category lookups.
        """
        return ItemService.list_active()

class ItemTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted items (Trash).
    Accessible only to Executives with 'delete_item' permission.
    """
    model = Item
    template_name = 'catalog/item_trash_list.html'
    context_object_name = 'items'
    permission_required = 'catalog.delete_item'
    raise_exception = True

    def get_queryset(self):
        return ItemService.list_deleted()

class ItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Form view for creating a new item.
    Utilizes ItemService for creation logic and audit tracking.
    """
    model = Item
    form_class = ItemForm
    template_name = 'catalog/item_form.html'
    success_url = reverse_lazy('catalog:item-list')
    permission_required = 'catalog.add_item'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'New Item'
        return context

    def form_valid(self, form):
        """
        Override form_valid to use ItemService for creation.
        """
        data = form.cleaned_data
        self.object = ItemService.create(
            sku=data['sku'],
            name=data['name'],
            unit=data['unit'],
            user=self.request.user,
            category=data['category'],
            express_sku=data['express_sku'],
            note=data['note'],
            status=data['status'],
            image=data.get('image')
        )
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())

class ItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Form view for updating an existing item.
    Utilizes ItemService for update logic and audit tracking.
    """
    model = Item
    form_class = ItemForm
    template_name = 'catalog/item_form.html'
    slug_field = 'sku'
    slug_url_kwarg = 'sku'
    permission_required = 'catalog.change_item'
    raise_exception = True

    def get_success_url(self):
        return reverse_lazy('catalog:item-detail', kwargs={'sku': self.object.sku})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update {self.object.name}"
        return context

    def form_valid(self, form):
        """
        Override form_valid to use ItemService for update.
        """
        self.object = ItemService.update(
            self.object,
            user=self.request.user,
            **form.cleaned_data
        )
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(self.get_success_url())

class ItemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a specific item.
    Shows item info, category, and audit trail.
    """
    model = Item
    template_name = 'catalog/item_detail.html'
    context_object_name = 'item'
    slug_field = 'sku'
    slug_url_kwarg = 'sku'
    permission_required = 'catalog.view_item'
    raise_exception = True

    def get_queryset(self):
        """
        Optimize queryset with related fields and filter for active.
        """
        return ItemService.get_active_queryset().select_related('created_by', 'updated_by')

class ItemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting an Item via ItemService.
    """
    model = Item
    template_name = 'catalog/item_confirm_delete.html'
    slug_field = 'sku'
    slug_url_kwarg = 'sku'
    permission_required = 'catalog.delete_item'
    success_url = reverse_lazy('catalog:item-list')
    raise_exception = True

    def get_queryset(self):
        return ItemService.get_active_queryset()

    def form_valid(self, form):
        try:
            ItemService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Item '{self.object.sku}' deleted successfully.")
            return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)

class ItemRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Item via ItemService.
    """
    permission_required = 'catalog.delete_item'
    raise_exception = True

    def post(self, request, sku):
        item = get_object_or_404(Item, sku=sku, is_deleted=True)
        try:
            ItemService.restore(item, user=request.user)
            messages.success(request, f"Item '{item.sku}' restored successfully.")
            return redirect('catalog:item-list')
        except Exception as e:
            messages.error(request, f"Unexpected error while restoring: {str(e)}")
            return redirect('catalog:item-trash')
