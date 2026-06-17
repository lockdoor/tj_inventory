from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
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

    def get_initial(self):
        initial = super().get_initial()
        initial['document_no'] = PurchaseOrderService.get_suggested_PO_numbers()
        return initial

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
                    
                    # Shortage IDs validation
                    shortage_ids_str = self.request.POST.get('linked_shortage_ids', '')
                    shortage_ids = [int(x) for x in shortage_ids_str.split(',') if x.strip().isdigit()]
                    
                    expected_date = header_data.get('expected_date')
                    if expected_date and shortage_ids:
                        from procurement.models import Shortage
                        from datetime import datetime, date
                        val_date = expected_date
                        if isinstance(val_date, str):
                            val_date = datetime.strptime(val_date, '%Y-%m-%d').date()
                        elif isinstance(val_date, datetime):
                            val_date = val_date.date()
                        
                        shortages_to_check = Shortage.objects.filter(id__in=shortage_ids, is_deleted=False)
                        for shortage in shortages_to_check:
                            if shortage.expected_date and val_date < shortage.expected_date:
                                raise ValidationError(
                                    f"Purchase Order expected date ({val_date.strftime('%Y-%m-%d')}) "
                                    f"cannot be earlier than shortage expected date of "
                                    f"{shortage.expected_date.strftime('%Y-%m-%d')} for {shortage.item.sku}."
                                )
                    
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
                    
                    # Link selected shortages
                    if shortage_ids:
                        from procurement.models import Shortage
                        from procurement.services.shortage_service import ShortageService
                        shortages = Shortage.objects.filter(id__in=shortage_ids, is_deleted=False, status=Shortage.Status.PENDING)
                        for shortage in shortages:
                            ShortageService.link_to_po(shortage, self.object, user=self.request.user)
                    
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
        
        # Add linked shortages data
        linked_shortages = self.object.shortages.filter(is_deleted=False)
        context['linked_shortages'] = linked_shortages
        context['linked_shortage_ids_str'] = ','.join(str(s.id) for s in linked_shortages)
        return context

    def form_valid(self, form):
        items = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
        if items.is_valid():
            try:
                with transaction.atomic():
                    # Collect header data
                    header_data = form.cleaned_data
                    
                    # Shortage IDs validation
                    shortage_ids_str = self.request.POST.get('linked_shortage_ids', '')
                    shortage_ids = [int(x) for x in shortage_ids_str.split(',') if x.strip().isdigit()]
                    
                    expected_date = header_data.get('expected_date')
                    if expected_date and shortage_ids:
                        from procurement.models import Shortage
                        from datetime import datetime, date
                        val_date = expected_date
                        if isinstance(val_date, str):
                            val_date = datetime.strptime(val_date, '%Y-%m-%d').date()
                        elif isinstance(val_date, datetime):
                            val_date = val_date.date()
                        
                        shortages_to_check = Shortage.objects.filter(id__in=shortage_ids, is_deleted=False)
                        for shortage in shortages_to_check:
                            if shortage.expected_date and val_date < shortage.expected_date:
                                raise ValidationError(
                                    f"Purchase Order expected date ({val_date.strftime('%Y-%m-%d')}) "
                                    f"cannot be earlier than shortage expected date of "
                                    f"{shortage.expected_date.strftime('%Y-%m-%d')} for {shortage.item.sku}."
                                )
                    
                    # Update PO using service
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
                    
                    # Unlink shortages that are no longer in the list
                    current_shortages = self.object.shortages.filter(is_deleted=False)
                    for shortage in current_shortages:
                        if shortage.id not in shortage_ids:
                            shortage.purchase_order = None
                            shortage.status = Shortage.Status.PENDING
                            shortage.updated_by = self.request.user
                            shortage.save()
                    
                    # Link newly added shortages
                    if shortage_ids:
                        from procurement.models import Shortage
                        from procurement.services.shortage_service import ShortageService
                        new_shortages = Shortage.objects.filter(id__in=shortage_ids, is_deleted=False).exclude(purchase_order=self.object)
                        for shortage in new_shortages:
                            ShortageService.link_to_po(shortage, self.object, user=self.request.user)
                    
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
        
        # Related Arrivals (ordered chronologically by expected arrival date)
        context['arrivals'] = self.object.arrivals.filter(
            is_deleted=False
        ).select_related('warehouse', 'partner').order_by('expected_date', 'created_at')
        
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

class PurchaseOrderCloseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'procurement.change_purchaseorder'

    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            PurchaseOrderService.close(po, user=request.user)
            messages.success(request, f"Purchase Order {po.document_no} closed successfully.")
        except ValidationError as e:
            messages.error(request, str(e))
            
        return redirect('procurement:purchase-order-detail', pk=pk)

class PurchaseOrderDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'procurement.delete_purchaseorder'

    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk, is_deleted=False)
        try:
            PurchaseOrderService.soft_delete(po, user=request.user)
            messages.success(request, f"Purchase Order {po.document_no} successfully deleted.")
            return redirect('procurement:purchase-order-list')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('procurement:purchase-order-detail', pk=pk)

from django.http import JsonResponse

class PurchaseOrderItemsAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        from django.db.models import Sum
        po = get_object_or_404(PurchaseOrder, pk=pk)
        items = po.items.all().select_related('item', 'packaging')
        exclude_arrival_id = request.GET.get('exclude_arrival')
        
        data_items = []
        for item in items:
            # Query all active expected arrivals for this PO line
            arrival_qs = item.arrival_items.filter(arrival__is_deleted=False).exclude(arrival__status='cancelled')
            if exclude_arrival_id:
                arrival_qs = arrival_qs.exclude(arrival_id=exclude_arrival_id)
            
            arrival_qty = arrival_qs.aggregate(total=Sum('expected_qty'))['total'] or 0
            
            data_items.append({
                'id': item.item.id,
                'sku': item.item.sku,
                'name': item.item.name,
                'packaging_id': item.packaging.id if item.packaging else None,
                'packaging_name': item.packaging.name if item.packaging else None,
                'unit': item.item.unit or 'pcs',
                'order_qty': float(item.order_qty),
                'arrival_qty': float(arrival_qty),
                'remaining_qty': max(0.0, float(item.order_qty) - float(arrival_qty)),
                'po_item_id': item.id
            })
            
        data = {
            'items': data_items,
            'partner_id': po.partner.id if po.partner else None
        }
        return JsonResponse(data)


class PendingShortagesAPIView(LoginRequiredMixin, View):
    def get(self, request):
        shortages = Shortage.objects.filter(
            status=Shortage.Status.PENDING,
            is_deleted=False
        ).select_related('item').order_by('-created_at')
        
        data_shortages = []
        for shortage in shortages:
            data_shortages.append({
                'id': shortage.id,
                'item_id': shortage.item.id,
                'item_sku': shortage.item.sku,
                'item_name': shortage.item.name,
                'item_unit': shortage.item.unit or 'pcs',
                'request_qty': float(shortage.request_qty),
                'reference_display': shortage.reference_display_name,
                'expected_date': shortage.expected_date.strftime('%Y-%m-%d') if shortage.expected_date else None,
                'note': shortage.note
            })
        return JsonResponse({'shortages': data_shortages})


from procurement.models import Shortage
from partners.models import Partner
from catalog.models import Item, ItemPackaging
import json
from django.db import IntegrityError

class PurchaseOrderCreateFromShortageView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'procurement.add_purchaseorder'
    template_name = 'procurement/purchase_order_from_shortage_form.html'
    
    def get(self, request, *args, **kwargs):
        shortage_ids_str = request.GET.get('shortage_ids', '')
        shortage_ids = [int(x) for x in shortage_ids_str.split(',') if x.strip().isdigit()]
        
        if not shortage_ids:
            messages.error(request, "No shortages were selected.")
            return redirect('procurement:shortage-list')
            
        shortages = Shortage.objects.filter(
            id__in=shortage_ids,
            status=Shortage.Status.PENDING,
            is_deleted=False
        ).select_related('item')
        
        if not shortages.exists():
            messages.error(request, "Selected shortages are either invalid, cancelled, or already ordered.")
            return redirect('procurement:shortage-list')

        if shortages.count() != len(shortage_ids):
            messages.error(request, "Invalid shortages detected, wrong amount of shortages selected.")
            return redirect('procurement:shortage-list')
            
        # Group shortages by item
        grouped_shortages = {}
        for shortage in shortages:
            item = shortage.item
            if item.id not in grouped_shortages:
                grouped_shortages[item.id] = {
                    'item': item,
                    'total_shortage_qty': 0,
                    'shortage_ids': [],
                    'expected_dates': set()
                }
            grouped_shortages[item.id]['total_shortage_qty'] += shortage.request_qty
            grouped_shortages[item.id]['shortage_ids'].append(shortage.id)
            if shortage.expected_date:
                grouped_shortages[item.id]['expected_dates'].add(shortage.expected_date)

        for group in grouped_shortages.values():
            dates = sorted(list(group['expected_dates']))
            if not dates:
                group['expected_date_display'] = "None"
            elif len(dates) == 1:
                group['expected_date_display'] = dates[0].strftime('%d %b %Y')
            else:
                group['expected_date_display'] = f"{dates[0].strftime('%d %b %Y')} to {dates[-1].strftime('%d %b %Y')}"
            
        # Find the maximum expected date among the selected shortages to prefill PO expected date
        expected_dates = [s.expected_date for s in shortages if s.expected_date]
        selected_expected_date_str = max(expected_dates).strftime('%Y-%m-%d') if expected_dates else ''

        # Suggested PO Number
        suggested_no = PurchaseOrderService.get_suggested_PO_numbers()
        
        # Suppliers
        suppliers = Partner.objects.filter(status='active', is_supplier=True, is_deleted=False)
        
        # System-wide pending shortage sum map (to let the user see total shortages per item)
        all_pending = Shortage.objects.filter(status=Shortage.Status.PENDING, is_deleted=False)
        from django.db.models import Sum
        shortage_sums = all_pending.values('item_id').annotate(total=Sum('request_qty'))
        shortage_sum_map = {entry['item_id']: float(entry['total']) for entry in shortage_sums}
        
        # Packagings for dropdown selection
        packagings = ItemPackaging.objects.filter(is_deleted=False)
        
        context = {
            'page_title': "Create Purchase Order from Shortages",
            'suggested_no': suggested_no,
            'selected_expected_date': selected_expected_date_str,
            'suppliers': suppliers,
            'grouped_shortages': grouped_shortages.values(),
            'shortage_ids_str': shortage_ids_str,
            'shortage_sum_map_json': json.dumps(shortage_sum_map),
            'packagings': packagings
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        partner_id = request.POST.get('partner')
        document_no = request.POST.get('document_no', '').strip()
        expected_date = request.POST.get('expected_date')
        note = request.POST.get('note', '').strip()
        shortage_ids_str = request.POST.get('shortage_ids', '')
        
        shortage_ids = [int(x) for x in shortage_ids_str.split(',') if x.strip().isdigit()]
        
        errors = []
        if not partner_id:
            errors.append("Supplier is required.")
        if not document_no:
            errors.append("Document Number is required.")
            
        partner = None
        if partner_id:
            try:
                partner = Partner.objects.get(pk=partner_id, is_supplier=True, is_deleted=False)
            except Partner.DoesNotExist:
                errors.append("Invalid Supplier selected.")
                
        # Parse item lines
        items_payload_json = request.POST.get('items_json')
        items_list = []
        if items_payload_json:
            try:
                raw_items = json.loads(items_payload_json)
                if not raw_items:
                    errors.append("At least one item line is required.")
                for ri in raw_items:
                    item_id = ri.get('item_id')
                    qty = ri.get('order_qty')
                    cost = ri.get('unit_cost')
                    packaging_id = ri.get('packaging_id')
                    
                    if not item_id or qty is None:
                        errors.append("Invalid item line format.")
                        continue
                        
                    from decimal import Decimal, InvalidOperation
                    try:
                        qty = Decimal(str(qty))
                    except (ValueError, InvalidOperation):
                        errors.append("Quantity must be a numeric value.")
                        continue
                        
                    if qty <= 0:
                        errors.append("Quantity must be greater than zero.")
                        continue

                    # Validate optional unit cost
                    if cost is None or str(cost).strip() == '':
                        cost_val = Decimal('0.00')
                    else:
                        try:
                            cost_val = Decimal(str(cost))
                        except (ValueError, InvalidOperation):
                            errors.append("Unit cost must be a numeric value.")
                            continue
                        if cost_val < 0:
                            errors.append("Unit cost cannot be negative.")
                            continue
                        
                    try:
                        item_obj = Item.objects.get(pk=item_id, is_deleted=False, status='active')
                    except Item.DoesNotExist:
                        errors.append("One or more selected products are invalid or inactive.")
                        continue
                        
                    packaging = None
                    if packaging_id:
                        try:
                            packaging = ItemPackaging.objects.get(pk=packaging_id, is_deleted=False)
                        except ItemPackaging.DoesNotExist:
                            errors.append("Invalid packaging selected.")
                            continue
                            
                    items_list.append({
                        'item': item_obj,
                        'order_qty': qty,
                        'unit_cost': cost_val,
                        'packaging': packaging
                    })
            except json.JSONDecodeError:
                errors.append("Invalid items structure submitted.")
        else:
            errors.append("No item lines submitted.")
            
        if errors:
            for err in errors:
                messages.error(request, err)
            return self._re_render_form(request, document_no, partner_id, expected_date, note, shortage_ids_str)
            
        try:
            with transaction.atomic():
                # Verify document_no uniqueness manually
                if PurchaseOrder.objects.filter(document_no=document_no, is_deleted=False).exists():
                    raise ValidationError(f"Purchase Order with Document Number '{document_no}' already exists.")
                    
                po = PurchaseOrderService.create_from_shortages(
                    document_no=document_no,
                    partner=partner,
                    user=request.user,
                    expected_date=expected_date if expected_date else None,
                    note=note,
                    items=items_list,
                    shortage_ids=shortage_ids
                )
                
            messages.success(request, f"Purchase Order {po.document_no} successfully created from shortages.")
            return redirect('procurement:purchase-order-list')
        except (ValidationError, IntegrityError, Exception) as e:
            messages.error(request, str(e))
            return self._re_render_form(request, document_no, partner_id, expected_date, note, shortage_ids_str)

    def _re_render_form(self, request, document_no, partner_id, expected_date, note, shortage_ids_str):
        shortage_ids = [int(x) for x in shortage_ids_str.split(',') if x.strip().isdigit()]
        shortages = Shortage.objects.filter(
            id__in=shortage_ids,
            status=Shortage.Status.PENDING,
            is_deleted=False
        ).select_related('item')
        
        grouped_shortages = {}
        for shortage in shortages:
            item = shortage.item
            if item.id not in grouped_shortages:
                grouped_shortages[item.id] = {
                    'item': item,
                    'total_shortage_qty': 0,
                    'shortage_ids': [],
                    'expected_dates': set()
                }
            grouped_shortages[item.id]['total_shortage_qty'] += shortage.request_qty
            grouped_shortages[item.id]['shortage_ids'].append(shortage.id)
            if shortage.expected_date:
                grouped_shortages[item.id]['expected_dates'].add(shortage.expected_date)

        for group in grouped_shortages.values():
            dates = sorted(list(group['expected_dates']))
            if not dates:
                group['expected_date_display'] = "None"
            elif len(dates) == 1:
                group['expected_date_display'] = dates[0].strftime('%d %b %Y')
            else:
                group['expected_date_display'] = f"{dates[0].strftime('%d %b %Y')} to {dates[-1].strftime('%d %b %Y')}"
            
        suppliers = Partner.objects.filter(status='active', is_supplier=True, is_deleted=False)
        all_pending = Shortage.objects.filter(status=Shortage.Status.PENDING, is_deleted=False)
        from django.db.models import Sum
        shortage_sums = all_pending.values('item_id').annotate(total=Sum('request_qty'))
        shortage_sum_map = {entry['item_id']: float(entry['total']) for entry in shortage_sums}
        packagings = ItemPackaging.objects.filter(is_deleted=False)
        
        context = {
            'page_title': "Create Purchase Order from Shortages",
            'suggested_no': document_no,
            'selected_partner_id': int(partner_id) if partner_id and partner_id.isdigit() else partner_id,
            'selected_expected_date': expected_date,
            'selected_note': note,
            'suppliers': suppliers,
            'grouped_shortages': grouped_shortages.values(),
            'shortage_ids_str': shortage_ids_str,
            'shortage_sum_map_json': json.dumps(shortage_sum_map),
            'packagings': packagings
        }
        return render(request, self.template_name, context)
