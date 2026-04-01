from django.shortcuts import render
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from catalog.models import Item
from catalog.services.item_service import ItemService

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
