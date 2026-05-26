import json
from django.views.generic import ListView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.db import transaction, IntegrityError
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from partners.models import Partner
from catalog.models import Item
from sales.models import SalesOrder
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

        context = {
            'page_title': "New Sales Order",
            'suggested_no': suggested_no,
            'customers': customers,
            'items_data_json': json.dumps(items_data),
            'items_list': items_data,
            'order_types': SalesOrder.OrderType.choices,
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
            'items__allocations__physical_reservation__stock__warehouse',
            'items__allocations__arrival_reservation__arrival_item__arrival__warehouse',
            'items__allocations__shortage'
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
        
        return context


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
                for item in order.items.all():
                    SalesService.refresh_allocation(item)
            messages.success(request, f"Allocations for Sales Order {order.document_no} successfully refreshed!")
        except Exception as e:
            messages.error(request, f"Error refreshing allocations: {str(e)}")

        return redirect('sales:sales-order-detail', pk=order.pk)


