from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError

from ..models import PurchaseOrder
from ..forms import PurchaseOrderForm, PurchaseOrderItemFormSet
from ..services.purchase_order_service import PurchaseOrderService

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'procurement/purchase_order_list.html'
    context_object_name = 'purchase_orders'
    permission_required = 'procurement.view_purchaseorder'
    ordering = ['-created_at']
    paginate_by = 10

    def get_queryset(self):
        return PurchaseOrderService.get_active_queryset().select_related('partner')

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
        items = PurchaseOrderItemFormSet(self.request.POST)
        if items.is_valid():
            try:
                with transaction.atomic():
                    # Collect header data
                    header_data = form.cleaned_data
                    
                    # Collect items data
                    items_data = []
                    for item_form in items:
                        if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                            items_data.append(item_form.cleaned_data)
                    
                    # Create PO using service
                    self.object = PurchaseOrderService.create(
                        document_no=header_data['document_no'],
                        partner=header_data['partner'],
                        user=self.request.user,
                        expected_date=header_data.get('expected_date'),
                        note=header_data.get('note', ''),
                        items=items_data
                    )
                    
                    messages.success(self.request, f"Purchase Order {self.object.document_no} created successfully.")
                    return redirect(self.success_url)
            except ValidationError as e:
                form.add_error(None, str(e))
                return self.form_invalid(form)
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
        items = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        if items.is_valid():
            try:
                with transaction.atomic():
                    # Update PO using service
                    header_data = form.cleaned_data
                    PurchaseOrderService.update(self.object, user=self.request.user, **header_data)
                    
                    # Collect items data for sync
                    items_data = []
                    for item_form in items:
                        if item_form.cleaned_data:
                            data = item_form.cleaned_data
                            data['instance'] = item_form.instance
                            data['is_deleted'] = item_form.cleaned_data.get('DELETE', False)
                            items_data.append(data)
                    
                    PurchaseOrderService.sync_items(self.object, items_data)
                    
                messages.success(self.request, f"Purchase Order {self.object.document_no} updated successfully.")
                return redirect(self.success_url)
            except ValidationError as e:
                form.add_error(None, str(e))
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)

class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'procurement/purchase_order_detail.html'
    context_object_name = 'po'
    permission_required = 'procurement.view_purchaseorder'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.all().select_related('item')
        
        # Attachments
        context['attachments'] = self.object.attachments.filter(is_deleted=False)
        from ..forms import PurchaseOrderAttachmentForm
        context['attachment_form'] = PurchaseOrderAttachmentForm()
        
        # Related Arrivals
        context['arrivals'] = self.object.arrivals.filter(is_deleted=False).select_related('warehouse', 'partner')
        
        return context

class PurchaseOrderSubmitView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'procurement.change_purchaseorder'

    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            PurchaseOrderService.submit(po, user=request.user)
            messages.success(request, f"Purchase Order {po.document_no} submitted successfully.")
        except ValidationError as e:
            messages.error(request, str(e))
            
        return redirect('procurement:purchase-order-detail', pk=pk)

class PurchaseOrderRevertView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'procurement.change_purchaseorder'

    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            PurchaseOrderService.revert_to_draft(po, user=request.user)
            messages.success(request, f"Purchase Order {po.document_no} reverted to Draft.")
        except ValidationError as e:
            messages.error(request, str(e))
            
        return redirect('procurement:purchase-order-detail', pk=pk)
from django.http import JsonResponse

class PurchaseOrderItemsAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        items = po.items.all().select_related('item', 'packaging')
        data = {
            'items': [
                {
                    'id': item.item.id,
                    'sku': item.item.sku,
                    'name': item.item.name,
                    'packaging_id': item.packaging.id if item.packaging else None,
                    'order_qty': float(item.order_qty),
                    'po_item_id': item.id
                } for item in items
            ],
            'partner_id': po.partner.id if po.partner else None
        }
        return JsonResponse(data)
