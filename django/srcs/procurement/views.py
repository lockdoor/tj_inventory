from django.views.generic import ListView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.db import transaction
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

from .models import PurchaseOrder
from .forms import PurchaseOrderForm, PurchaseOrderItemFormSet

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'procurement/purchase_order_list.html'
    context_object_name = 'purchase_orders'
    permission_required = 'procurement.view_purchaseorder'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False).select_related('partner')

class PurchaseOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'procurement/purchase_order_form.html'
    permission_required = 'procurement.add_purchaseorder'
    success_url = reverse_lazy('procurement:purchase-order-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = PurchaseOrderItemFormSet(self.request.POST)
        else:
            context['items'] = PurchaseOrderItemFormSet()
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
            messages.success(self.request, f"Purchase Order {self.object.document_no} created successfully.")
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)

class PurchaseOrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'procurement/purchase_order_form.html'
    permission_required = 'procurement.change_purchaseorder'
    success_url = reverse_lazy('procurement:purchase-order-list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.status != PurchaseOrder.Status.DRAFT:
            raise PermissionDenied("Only Draft Purchase Orders can be edited.")
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        else:
            context['items'] = PurchaseOrderItemFormSet(instance=self.object)
        context['is_update'] = True
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            with transaction.atomic():
                form.instance.updated_by = self.request.user
                self.object = form.save()
                items.save()
            messages.success(self.request, f"Purchase Order {self.object.document_no} updated successfully.")
            return redirect(self.success_url)
        else:
            return self.form_invalid(form)
