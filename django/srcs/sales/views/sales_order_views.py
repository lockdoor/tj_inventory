import json
from django.views.generic import ListView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Prefetch
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from partners.models import Partner
from catalog.models import Item
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from inventory.models import Stock, StockReservation
from procurement.models import ArrivalItem, ArrivalReservation
from sales.services.sales_service import SalesService

class SalesOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Paginated search-enabled table listing active sales orders.
    """
    model = SalesOrder
    template_name = 'sales/sales_order_list.html'
    context_object_name = 'sales_orders'
    permission_required = 'sales.view_salesorder'
    raise_exception = True
    paginate_by = 10

    def get_queryset(self):
        # Retrieve active non-deleted queryset, ordered newest first
        queryset = SalesService.get_active_queryset().order_by('-order_date', '-created_at')
        
        q = self.request.GET.get('q')
        if q:
            q = q.strip()
            queryset = queryset.filter(
                Q(document_no__icontains=q) |
                Q(partner__name__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Sales Orders"
        context['q'] = self.request.GET.get('q', '')
        return context


class SalesOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Interactive, shopping cart style sales order creation view.
    """
    permission_required = 'sales.add_salesorder'
    raise_exception = True
    template_name = 'sales/sales_order_create.html'

    def get(self, request, *args, **kwargs):
        # Auto-generate dynamic document_no prefix + increment
        today_str = timezone.now().strftime('%Y%m%d')
        prefix = f"SO-{today_str}-"
        last_so = SalesOrder.objects.filter(document_no__startswith=prefix).order_by('-document_no').first()
        if last_so:
            try:
                last_serial = int(last_so.document_no.split('-')[-1])
                new_serial = last_serial + 1
            except ValueError:
                new_serial = 1
        else:
            new_serial = 1
        suggested_no = f"{prefix}{new_serial:04d}"

        # Fetch active customers
        customers = Partner.objects.filter(is_customer=True, is_deleted=False, status='active')

        # Fetch active catalog items with their stock lots and reservations preloaded
        items = Item.objects.filter(is_deleted=False, status='active').prefetch_related(
            'stocks__reservations',
            'images',
            'packagings'
        )

        items_data = []
        for item in items:
            total_balance = 0
            total_reserved = 0
            lots_data = []
            packagings_data = []

            for pkg in item.packagings.filter(is_deleted=False, status='active'):
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'quantity': int(pkg.quantity),
                })

            for stock in item.stocks.filter(is_deleted=False, status='active').exclude(balance=0):
                total_balance += stock.balance
                total_reserved += stock.reserved_qty
                
                res_list = []
                for res in stock.reservations.all():
                    res_list.append({
                        'reference_no': res.reference_no,
                        'reference_type': res.get_reference_type_display(),
                        'quantity': float(res.quantity),
                        'created_by': res.created_by.username if res.created_by else 'System',
                        'note': res.note
                    })

                lots_data.append({
                    'lot_number': stock.lot_number,
                    'balance': float(stock.balance),
                    'reserved_qty': float(stock.reserved_qty),
                    'available_qty': float(stock.available_qty),
                    'exp_date': stock.exp_date.strftime('%Y-%m-%d') if stock.exp_date else 'N/A',
                    'reservations': res_list
                })

            items_data.append({
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
                'unit': item.unit,
                'main_image_url': item.main_image.image.url if item.main_image else None,
                'total_balance': float(total_balance),
                'total_reserved': float(total_reserved),
                'total_available': float(max(0, total_balance - total_reserved)),
                'lots': lots_data,
                'packagings': packagings_data
            })

        from django.urls import reverse
        context = {
            'page_title': "New Sales Order",
            'suggested_no': suggested_no,
            'customers': customers,
            'items_data_json': json.dumps(items_data),
            'items_list': items_data,
            'order_types': SalesOrder.OrderType.choices,
            'form_action_url': reverse('sales:sales-order-create'),
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        partner_id = request.POST.get('partner')
        order_type = request.POST.get('order_type', SalesOrder.OrderType.NORMAL)
        order_date = request.POST.get('order_date')
        document_no = request.POST.get('document_no', '').strip()
        note = request.POST.get('note', '').strip()
        items_json = request.POST.get('items_json')

        errors = []

        if not partner_id:
            errors.append("Customer (Partner) is required.")
        if not document_no:
            errors.append("Document Number is required.")

        partner = None
        if partner_id:
            try:
                partner = Partner.objects.get(pk=partner_id, is_deleted=False, is_customer=True)
            except (Partner.DoesNotExist, ValueError):
                errors.append("Invalid Customer selected.")

        items_list = []
        if items_json:
            try:
                cart_items = json.loads(items_json)
                if not cart_items:
                    errors.append("You must add at least one item to create a Sales Order.")
                for cart_item in cart_items:
                    item_id = cart_item.get('item_id')
                    qty = cart_item.get('requested_qty')
                    price = cart_item.get('unit_price')

                    if not item_id or qty is None or price is None:
                        errors.append("Invalid item line format.")
                        continue

                    from decimal import Decimal, InvalidOperation
                    try:
                        qty = Decimal(str(qty))
                        price = Decimal(str(price))
                    except (ValueError, InvalidOperation):
                        errors.append("Quantity and Price must be numeric values.")
                        continue

                    if qty <= 0:
                        errors.append("Quantity must be greater than zero.")
                        continue
                    if price < 0:
                        errors.append("Unit price cannot be negative.")
                        continue

                    try:
                        item = Item.objects.get(pk=item_id, is_deleted=False, status='active')
                        items_list.append({
                            'item': item,
                            'requested_qty': qty,
                            'unit_price': price
                        })
                    except Item.DoesNotExist:
                        errors.append("One or more selected items do not exist or are inactive.")
            except json.JSONDecodeError:
                errors.append("Shopping cart data format is invalid.")
        else:
            errors.append("Shopping cart is empty.")

        if errors:
            for err in errors:
                messages.error(request, err)
            return self._re_render_form(request, document_no, partner_id, order_type, order_date, note, items_json)

        try:
            with transaction.atomic():
                # Check uniqueness manually to give a clean message
                if SalesOrder.objects.filter(document_no=document_no, is_deleted=False).exists():
                    raise ValidationError(f"Sales Order with Document Number '{document_no}' already exists.")

                order = SalesService.create_order(
                    document_no=document_no,
                    partner=partner,
                    user=request.user,
                    order_date=order_date if order_date else None,
                    order_type=order_type,
                    items=items_list,
                    note=note
                )
            
            messages.success(request, f"Sales Order {order.document_no} successfully created!")
            return redirect('sales:sales-order-list')

        except (ValidationError, IntegrityError, Exception) as e:
            messages.error(request, str(e))
            return self._re_render_form(request, document_no, partner_id, order_type, order_date, note, items_json)

    def _re_render_form(self, request, document_no, partner_id, order_type, order_date, note, items_json):
        # Fetch active customers
        customers = Partner.objects.filter(is_customer=True, is_deleted=False, status='active')

        # Fetch active catalog items
        items = Item.objects.filter(is_deleted=False, status='active').prefetch_related(
            'stocks__reservations',
            'images',
            'packagings'
        )

        items_data = []
        for item in items:
            total_balance = 0
            total_reserved = 0
            lots_data = []
            packagings_data = []

            for pkg in item.packagings.filter(is_deleted=False, status='active'):
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'quantity': int(pkg.quantity),
                })

            for stock in item.stocks.filter(is_deleted=False, status='active'):
                total_balance += stock.balance
                total_reserved += stock.reserved_qty
                
                res_list = []
                for res in stock.reservations.all():
                    res_list.append({
                        'reference_no': res.reference_no,
                        'reference_type': res.get_reference_type_display(),
                        'quantity': float(res.quantity),
                        'created_by': res.created_by.username if res.created_by else 'System',
                        'note': res.note
                    })

                lots_data.append({
                    'lot_number': stock.lot_number,
                    'balance': float(stock.balance),
                    'reserved_qty': float(stock.reserved_qty),
                    'available_qty': float(stock.available_qty),
                    'exp_date': stock.exp_date.strftime('%Y-%m-%d') if stock.exp_date else 'N/A',
                    'reservations': res_list
                })

            items_data.append({
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
                'unit': item.unit,
                'main_image_url': item.main_image.image.url if item.main_image else None,
                'total_balance': float(total_balance),
                'total_reserved': float(total_reserved),
                'total_available': float(max(0, total_balance - total_reserved)),
                'lots': lots_data,
                'packagings': packagings_data
            })

        from django.urls import reverse
        context = {
            'page_title': "New Sales Order",
            'suggested_no': document_no,
            'selected_partner_id': int(partner_id) if partner_id and partner_id.isdigit() else partner_id,
            'selected_order_type': order_type,
            'selected_order_date': order_date,
            'selected_note': note,
            'prepopulated_items_json': items_json,
            'customers': customers,
            'items_data_json': json.dumps(items_data),
            'items_list': items_data,
            'order_types': SalesOrder.OrderType.choices,
            'form_action_url': reverse('sales:sales-order-create'),
        }
        return render(request, self.template_name, context)


class SalesOrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Interactive, shopping cart style sales order editing view (only for Draft status).
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True
    template_name = 'sales/sales_order_create.html'

    def get(self, request, *args, **kwargs):
        order = get_object_or_404(SalesOrder, pk=self.kwargs.get('pk'), is_deleted=False)

        # Gating: only Draft orders can be edited
        if order.status != SalesOrder.Status.DRAFT:
            messages.error(request, "Only draft sales orders can be edited.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        # Fetch active customers
        customers = Partner.objects.filter(is_customer=True, is_deleted=False, status='active')

        # Fetch active catalog items with their stock lots and reservations preloaded
        items = Item.objects.filter(is_deleted=False, status='active').prefetch_related(
            'stocks__reservations',
            'images',
            'packagings'
        )

        items_data = []
        for item in items:
            total_balance = 0
            total_reserved = 0
            lots_data = []
            packagings_data = []

            for pkg in item.packagings.filter(is_deleted=False, status='active'):
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'quantity': int(pkg.quantity),
                })

            for stock in item.stocks.filter(is_deleted=False, status='active'):
                total_balance += stock.balance
                total_reserved += stock.reserved_qty
                
                res_list = []
                for res in stock.reservations.all():
                    res_list.append({
                        'reference_no': res.reference_no,
                        'reference_type': res.get_reference_type_display(),
                        'quantity': float(res.quantity),
                        'created_by': res.created_by.username if res.created_by else 'System',
                        'note': res.note
                    })

                lots_data.append({
                    'lot_number': stock.lot_number,
                    'balance': float(stock.balance),
                    'reserved_qty': float(stock.reserved_qty),
                    'available_qty': float(stock.available_qty),
                    'exp_date': stock.exp_date.strftime('%Y-%m-%d') if stock.exp_date else 'N/A',
                    'reservations': res_list
                })

            items_data.append({
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
                'unit': item.unit,
                'main_image_url': item.main_image.image.url if item.main_image else None,
                'total_balance': float(total_balance),
                'total_reserved': float(total_reserved),
                'total_available': float(max(0, total_balance - total_reserved)),
                'lots': lots_data,
                'packagings': packagings_data
            })

        # Prepopulate items json with current order items
        prepopulated_items = []
        for line in order.items.all():
            prepopulated_items.append({
                'item_id': line.item.pk,
                'requested_qty': float(line.requested_qty),
                'unit_price': float(line.unit_price)
            })

        from django.urls import reverse
        context = {
            'page_title': f"Edit Sales Order: {order.document_no}",
            'breadcrumb_title': "Edit Sales Order",
            'suggested_no': order.document_no,
            'selected_partner_id': order.partner.pk,
            'selected_order_type': order.order_type,
            'selected_order_date': order.order_date.strftime('%Y-%m-%d') if order.order_date else '',
            'selected_note': order.note,
            'prepopulated_items_json': json.dumps(prepopulated_items),
            'customers': customers,
            'items_data_json': json.dumps(items_data),
            'items_list': items_data,
            'order_types': SalesOrder.OrderType.choices,
            'form_action_url': reverse('sales:sales-order-edit', kwargs={'pk': order.pk}),
            'submit_button_text': "Save Sales Order Changes",
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(SalesOrder, pk=self.kwargs.get('pk'), is_deleted=False)

        if order.status != SalesOrder.Status.DRAFT:
            messages.error(request, "Only draft sales orders can be edited.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        partner_id = request.POST.get('partner')
        order_type = request.POST.get('order_type', SalesOrder.OrderType.NORMAL)
        order_date = request.POST.get('order_date')
        document_no = request.POST.get('document_no', '').strip()
        note = request.POST.get('note', '').strip()
        items_json = request.POST.get('items_json')

        errors = []

        if not partner_id:
            errors.append("Customer (Partner) is required.")
        if not document_no:
            errors.append("Document Number is required.")

        partner = None
        if partner_id:
            try:
                partner = Partner.objects.get(pk=partner_id, is_deleted=False, is_customer=True)
            except (Partner.DoesNotExist, ValueError):
                errors.append("Invalid Customer selected.")

        items_list = []
        if items_json:
            try:
                cart_items = json.loads(items_json)
                if not cart_items:
                    errors.append("You must add at least one item to edit a Sales Order.")
                for cart_item in cart_items:
                    item_id = cart_item.get('item_id')
                    qty = cart_item.get('requested_qty')
                    price = cart_item.get('unit_price')

                    if not item_id or qty is None or price is None:
                        errors.append("Invalid item line format.")
                        continue

                    from decimal import Decimal, InvalidOperation
                    try:
                        qty = Decimal(str(qty))
                        price = Decimal(str(price))
                    except (ValueError, InvalidOperation):
                        errors.append("Quantity and Price must be numeric values.")
                        continue

                    if qty <= 0:
                        errors.append("Quantity must be greater than zero.")
                        continue
                    if price < 0:
                        errors.append("Unit price cannot be negative.")
                        continue

                    try:
                        item = Item.objects.get(pk=item_id, is_deleted=False, status='active')
                        items_list.append({
                            'item': item,
                            'requested_qty': qty,
                            'unit_price': price
                        })
                    except Item.DoesNotExist:
                        errors.append("One or more selected items do not exist or are inactive.")
            except json.JSONDecodeError:
                errors.append("Shopping cart data format is invalid.")
        else:
            errors.append("Shopping cart is empty.")

        if errors:
            for err in errors:
                messages.error(request, err)
            return self._re_render_form(request, order, document_no, partner_id, order_type, order_date, note, items_json)

        try:
            with transaction.atomic():
                # Check uniqueness manually to give a clean message (excluding this order itself!)
                if SalesOrder.objects.filter(document_no=document_no, is_deleted=False).exclude(pk=order.pk).exists():
                    raise ValidationError(f"Sales Order with Document Number '{document_no}' already exists.")

                SalesService.update_order(
                    order=order,
                    document_no=document_no,
                    partner=partner,
                    user=request.user,
                    order_date=order_date if order_date else None,
                    order_type=order_type,
                    items=items_list,
                    note=note
                )
            
            messages.success(request, f"Sales Order {order.document_no} successfully updated!")
            return redirect('sales:sales-order-detail', pk=order.pk)

        except (ValidationError, IntegrityError, Exception) as e:
            messages.error(request, str(e))
            return self._re_render_form(request, order, document_no, partner_id, order_type, order_date, note, items_json)

    def _re_render_form(self, request, order, document_no, partner_id, order_type, order_date, note, items_json):
        # Fetch active customers
        customers = Partner.objects.filter(is_customer=True, is_deleted=False, status='active')

        # Fetch active catalog items
        items = Item.objects.filter(is_deleted=False, status='active').prefetch_related(
            'stocks__reservations',
            'images',
            'packagings'
        )

        items_data = []
        for item in items:
            total_balance = 0
            total_reserved = 0
            lots_data = []
            packagings_data = []

            for pkg in item.packagings.filter(is_deleted=False, status='active'):
                packagings_data.append({
                    'id': pkg.id,
                    'name': pkg.name,
                    'quantity': int(pkg.quantity),
                })

            for stock in item.stocks.filter(is_deleted=False, status='active'):
                total_balance += stock.balance
                total_reserved += stock.reserved_qty
                
                res_list = []
                for res in stock.reservations.all():
                    res_list.append({
                        'reference_no': res.reference_no,
                        'reference_type': res.get_reference_type_display(),
                        'quantity': float(res.quantity),
                        'created_by': res.created_by.username if res.created_by else 'System',
                        'note': res.note
                    })

                lots_data.append({
                    'lot_number': stock.lot_number,
                    'balance': float(stock.balance),
                    'reserved_qty': float(stock.reserved_qty),
                    'available_qty': float(stock.available_qty),
                    'exp_date': stock.exp_date.strftime('%Y-%m-%d') if stock.exp_date else 'N/A',
                    'reservations': res_list
                })

            items_data.append({
                'id': item.id,
                'sku': item.sku,
                'name': item.name,
                'unit': item.unit,
                'main_image_url': item.main_image.image.url if item.main_image else None,
                'total_balance': float(total_balance),
                'total_reserved': float(total_reserved),
                'total_available': float(max(0, total_balance - total_reserved)),
                'lots': lots_data,
                'packagings': packagings_data
            })

        from django.urls import reverse
        context = {
            'page_title': f"Edit Sales Order: {document_no}",
            'breadcrumb_title': "Edit Sales Order",
            'suggested_no': document_no,
            'selected_partner_id': int(partner_id) if partner_id and partner_id.isdigit() else partner_id,
            'selected_order_type': order_type,
            'selected_order_date': order_date,
            'selected_note': note,
            'prepopulated_items_json': items_json,
            'customers': customers,
            'items_data_json': json.dumps(items_data),
            'items_list': items_data,
            'order_types': SalesOrder.OrderType.choices,
            'form_action_url': reverse('sales:sales-order-edit', kwargs={'pk': order.pk}),
            'submit_button_text': "Save Sales Order Changes",
        }
        return render(request, self.template_name, context)


class SalesOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed diagnostic view for a single Sales Order.
    Shows customers info, total finances, and nested items allocation status (Physical/Future/Shortage).
    """
    model = SalesOrder
    template_name = 'sales/sales_order_detail.html'
    context_object_name = 'sales_order'
    permission_required = 'sales.view_salesorder'
    raise_exception = True

    def get_queryset(self):
        return SalesOrder.objects.filter(is_deleted=False).select_related(
            'partner',
            'created_by',
            'updated_by'
        ).prefetch_related(
            'items__item',
            Prefetch(
                'items__allocations',
                queryset=SalesAllocation.objects.filter(is_deleted=False).select_related(
                    'physical_reservation__stock__warehouse',
                    'arrival_reservation__arrival_item__arrival__warehouse',
                    'shortage'
                )
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.object
        context['page_title'] = f"Sales Order: {order.document_no}"
        
        # Compute order total financial metrics
        total_amount = sum(item.requested_qty * item.unit_price for item in order.items.all())
        context['total_amount'] = float(total_amount)
        
        # Calculate overall order allocation status progress
        total_items = order.items.count()
        allocated_items = order.items.filter(status='allocated').count()
        context['allocated_items'] = allocated_items
        context['total_items'] = total_items
        
        # Attachments context
        context['attachments'] = order.attachments.filter(is_deleted=False)
        from sales.forms.attachment_forms import SalesOrderAttachmentForm
        context['attachment_form'] = SalesOrderAttachmentForm()
        
        # Linked Outbound Movements (WMS)
        from inventory.models import InventoryMovement
        context['wms_movements'] = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            reference_no=order.document_no,
            is_deleted=False
        ).select_related('warehouse').order_by('-created_at')
        
        return context


def check_and_promote_order_status(order):
    """
    Evaluates order-level status based on allocations:
    - If shortages exist: order status MUST be/remain DRAFT.
    - If no shortages but arrivals exist: order status is PREORDER (if it was CONFIRMED/PREORDER).
    - If no shortages and no arrivals: order status is promoted to CONFIRMED.
    """
    from sales.models import SalesAllocation
    
    # We only auto-promote/auto-demote orders in DRAFT, PREORDER, or CONFIRMED statuses
    if order.status not in [order.Status.DRAFT, order.Status.PREORDER, order.Status.CONFIRMED]:
        return False
        
    has_shortages = False
    has_arrivals = False
    for item in order.items.all():
        if item.allocations.filter(source_type=SalesAllocation.SourceType.SHORTAGE, is_deleted=False).exists():
            has_shortages = True
        if item.allocations.filter(source_type=SalesAllocation.SourceType.ARRIVAL, is_deleted=False).exists():
            has_arrivals = True
            
    if has_shortages:
        if order.status != order.Status.DRAFT:
            order.status = order.Status.DRAFT
            order.save(update_fields=['status', 'updated_at', 'version'])
            return True
        return False
    elif has_arrivals:
        if order.status == order.Status.DRAFT:
            # We don't auto-confirm a draft order to preorder without explicit action
            return False
        elif order.status != order.Status.PREORDER:
            order.status = order.Status.PREORDER
            order.save(update_fields=['status', 'updated_at', 'version'])
            return True
        return False
    else:
        # 100% physically allocated
        if order.status in [order.Status.DRAFT, order.Status.PREORDER] and order.items.exists():
            order.status = order.Status.CONFIRMED
            order.save(update_fields=['status', 'updated_at', 'version'])
            return True
        return False


class SalesOrderRefreshAllocationView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST-only action to trigger the smart allocation engine (gap filler)
    for all items within the Sales Order.
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('pk')
        order = get_object_or_404(SalesOrder, pk=order_id, is_deleted=False)
        
        # Gating: Cancelled and Shipped orders cannot have allocations refreshed
        if order.status in [SalesOrder.Status.CANCELLED, SalesOrder.Status.SHIPPED]:
            messages.error(request, f"Cannot refresh allocations for {order.get_status_display()} orders.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        # Trigger refresh on each item line within transaction
        try:
            with transaction.atomic():
                old_status = order.status
                
                for item in order.items.all():
                    SalesService.refresh_allocation(item)
                
                # Check for status changes
                status_changed = check_and_promote_order_status(order)
                new_status = order.status
                
            if status_changed:
                if new_status == SalesOrder.Status.DRAFT:
                    messages.warning(request, f"Allocations refreshed! Sales Order {order.document_no} has outstanding shortages and has been demoted to DRAFT status.")
                elif new_status == SalesOrder.Status.CONFIRMED:
                    messages.success(request, f"Allocations refreshed! Sales Order {order.document_no} is now fully allocated and promoted to CONFIRMED status.")
                elif new_status == SalesOrder.Status.PREORDER:
                    messages.success(request, f"Allocations refreshed! Sales Order {order.document_no} status updated to Pre-order.")
            else:
                messages.success(request, f"Allocations for Sales Order {order.document_no} successfully refreshed!")
        except Exception as e:
            messages.error(request, f"Error refreshing allocations: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)


class SalesOrderConfirmView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST-only action to explicitly confirm a DRAFT Sales Order.
    If all items are physical stock, transitions to CONFIRMED.
    Otherwise, transitions to PREORDER (if arrivals exist) or remains DRAFT (if shortages exist).
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('pk')
        order = get_object_or_404(SalesOrder, pk=order_id, is_deleted=False)

        if order.status != SalesOrder.Status.DRAFT:
            messages.error(request, "Only Draft orders can be confirmed.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        try:
            with transaction.atomic():
                # 1. Refresh allocations to get latest status
                for item in order.items.all():
                    SalesService.refresh_allocation(item)

                # 2. Check for shortages or arrivals
                from sales.models import SalesAllocation
                has_shortages = False
                has_arrivals = False
                for item in order.items.all():
                    if item.allocations.filter(source_type=SalesAllocation.SourceType.SHORTAGE, is_deleted=False).exists():
                        has_shortages = True
                    if item.allocations.filter(source_type=SalesAllocation.SourceType.ARRIVAL, is_deleted=False).exists():
                        has_arrivals = True

                if has_shortages:
                    # Shortage is not fulfill! Block confirmation and keep as DRAFT
                    msg = f"Sales Order {order.document_no} cannot be confirmed because it has outstanding shortages. Order remains in Draft."
                    messages.error(request, msg)
                else:
                    if has_arrivals:
                        order.status = SalesOrder.Status.PREORDER
                        msg = f"Sales Order {order.document_no} confirmed as Pre-order due to outstanding scheduled arrivals."
                    else:
                        order.status = SalesOrder.Status.CONFIRMED
                        msg = f"Sales Order {order.document_no} confirmed and locked successfully as Confirmed!"
                    
                    order.updated_by = request.user
                    order.save(update_fields=['status', 'updated_by', 'updated_at', 'version'])
                    messages.success(request, msg)

        except Exception as e:
            messages.error(request, f"Error confirming order: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)


class SalesOrderReleaseToWarehouseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST-only action to release a CONFIRMED Sales Order to the warehouse.
    Atomically updates status to PROCESSING and generates a Draft Outbound Movement.
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        order_id = self.kwargs.get('pk')
        order = get_object_or_404(SalesOrder, pk=order_id, is_deleted=False)

        if order.status != SalesOrder.Status.CONFIRMED:
            messages.error(request, f"Cannot release Sales Order {order.document_no} because its status is '{order.get_status_display()}'. Only Confirmed orders can be released to the warehouse.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        try:
            from inventory.services.movement_service import MovementService
            with transaction.atomic():
                # 1. Update status to PROCESSING
                order.status = SalesOrder.Status.PROCESSING
                order.updated_by = request.user
                order.save(update_fields=['status', 'updated_by', 'updated_at', 'version'])

                # 2. Trigger Draft Movement generation
                movements = MovementService.create_outbound_from_reservations(order, request.user)

            messages.success(
                request, 
                f"Sales Order {order.document_no} successfully released to warehouse! "
                f"Draft Outbound Movement(s) generated for picking."
            )
        except Exception as e:
            messages.error(request, f"Error releasing order to warehouse: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)


class SalesOrderItemAllocateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Dedicated view to manage manual reservations for a single Sales Order Item line.
    GET: Displays available Stocks and expected Arrivals side-by-side.
    POST: Clears prior allocations, registers manual picks, and automatically logs shortages for remaining gaps.
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True
    template_name = 'sales/sales_order_allocate.html'

    def get(self, request, *args, **kwargs):
        order_item = get_object_or_404(SalesOrderItem, pk=self.kwargs.get('item_pk'))
        order = order_item.order
        item = order_item.item

        # Gating protection
        if order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Cannot manually allocate items for orders that are not in Draft status.")

        # 1. Map existing allocations (both manual and automatic) to pre-fill inputs
        stock_alloc_map = {}
        arrival_alloc_map = {}
        for alloc in order_item.allocations.filter(is_deleted=False):
            if alloc.source_type == SalesAllocation.SourceType.STOCK and alloc.physical_reservation and not alloc.physical_reservation.is_deleted:
                stock_alloc_map[alloc.physical_reservation.stock.pk] = float(alloc.quantity)
            elif alloc.source_type == SalesAllocation.SourceType.ARRIVAL and alloc.arrival_reservation:
                arrival_alloc_map[alloc.arrival_reservation.arrival_item.pk] = float(alloc.quantity)

        # 2. Fetch active physical stock lots with non-zero available quantity
        stocks = Stock.objects.filter(
            item=item,
            is_deleted=False,
            status='active'
        ).exclude(balance=0).select_related('warehouse').order_by('exp_date', 'created_at')

        # 3. Fetch expected arrivals preloaded (must arrive on or before order expected date)
        arrival_items = ArrivalItem.objects.filter(
            item=item,
            arrival__status__in=['scheduled', 'receiving'],
            arrival__expected_date__lte=order.order_date,
            arrival__is_deleted=False
        ).select_related('arrival__warehouse', 'arrival').order_by('arrival__expected_date')

        # 4. Pre-populate UI inputs with the stored previous manual reservation quantities
        for s in stocks:
            s.allocated_qty = stock_alloc_map.get(s.pk, 0.0)
            s.available_qty_for_ui = float(s.available_qty) + s.allocated_qty

        for ai in arrival_items:
            ai.allocated_qty = arrival_alloc_map.get(ai.pk, 0.0)
            ai.available_qty_for_ui = float(ai.available_qty) + ai.allocated_qty

        context = {
            'page_title': f"Allocate Sourcing: {item.sku}",
            'order_item': order_item,
            'order': order,
            'item': item,
            'stocks': stocks,
            'arrival_items': arrival_items,
        }
        return render(request, self.template_name, context)
 
    def post(self, request, *args, **kwargs):
        order_item = get_object_or_404(SalesOrderItem, pk=self.kwargs.get('item_pk'))
        order = order_item.order
 
        # Gating protection
        if order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Cannot manually allocate items for orders that are not in Draft status.")

        from decimal import Decimal, InvalidOperation

        # Parse submitted quantities from POST
        submitted_stock_qtys = {}
        submitted_arrival_qtys = {}
        for key, val in request.POST.items():
            if not val or val.strip() == '':
                continue
            try:
                qty = Decimal(val)
            except (ValueError, InvalidOperation):
                continue
            if qty < 0:
                continue
            
            if key.startswith('stock_qty_'):
                stock_id = int(key.split('_')[-1])
                submitted_stock_qtys[stock_id] = qty
            elif key.startswith('arrival_qty_'):
                arrival_item_id = int(key.split('_')[-1])
                submitted_arrival_qtys[arrival_item_id] = qty

        try:
            SalesService.save_manual_allocations(
                order_item,
                request.user,
                submitted_stock_qtys,
                submitted_arrival_qtys
            )
            messages.success(request, f"Manual reservations for {order_item.item.sku} saved successfully.")
        except Exception as e:
            messages.error(request, f"Error saving reservations: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)


class SalesOrderItemResetAllocationView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST-only action to reset all manual allocations back to automatic.
    """
    permission_required = 'sales.change_salesorder'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        order_item = get_object_or_404(SalesOrderItem, pk=self.kwargs.get('item_pk'))
        order = order_item.order

        if order.status != SalesOrder.Status.DRAFT:
            raise ValidationError("Cannot modify allocations for orders that are not in Draft status.")

        try:
            SalesService.reset_allocations(order_item, request.user)
            if request.method == 'GET':
                messages.info(request, f"Manual sourcing cancelled. Sourcing for {order_item.item.sku} restored to automatic.")
            else:
                messages.success(request, f"Allocations for {order_item.item.sku} successfully reset to automatic.")
        except Exception as e:
            messages.error(request, f"Error resetting allocations: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)


class SalesOrderRevertToDraftView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """POST-only action to revert a Confirmed or Pre-order Sales Order back to Draft status."""
    permission_required = 'sales.change_salesorder'
    raise_exception = True

    def post(self, request, pk):
        order = get_object_or_404(SalesOrder, pk=pk, is_deleted=False)

        if order.status not in [SalesOrder.Status.CONFIRMED, SalesOrder.Status.PREORDER]:
            messages.error(request, "Only Confirmed or Pre-order orders can be reverted to draft.")
            return redirect('sales:sales-order-detail', pk=order.pk)

        try:
            with transaction.atomic():
                # We PRESERVE all allocations and reservations intact!
                # We only reset fulfilled_qty to 0.00 and restore appropriate item statuses based on allocations
                for item in order.items.all():
                    item.fulfilled_qty = 0.00
                    
                    if item.allocated_qty >= item.requested_qty:
                        item.status = SalesOrderItem.Status.ALLOCATED
                    elif item.allocated_qty > 0:
                        item.status = SalesOrderItem.Status.PARTIAL
                    else:
                        item.status = SalesOrderItem.Status.PENDING
                    
                    item.save(update_fields=['status', 'fulfilled_qty'])
                
                # Transition order status back to DRAFT
                order.status = SalesOrder.Status.DRAFT
                order.updated_by = request.user
                order.save(update_fields=['status', 'updated_by', 'updated_at', 'version'])

            messages.success(request, f"Sales Order {order.document_no} successfully reverted to Draft. Allocations and reservations have been preserved.")
        except Exception as e:
            messages.error(request, f"Error reverting order to Draft: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)




