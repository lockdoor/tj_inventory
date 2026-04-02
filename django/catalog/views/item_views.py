from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from catalog.models import Item
from catalog.services.item_service import ItemService
from catalog.forms import ItemForm

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
            status=data['status']
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
        Optimize queryset with related fields.
        """
        return Item.objects.select_related('category', 'created_by', 'updated_by')
