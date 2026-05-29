import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from partners.models import Partner
from sales.models import SalesOrder, SalesOrderItem
from sales.services.sales_service import SalesService
from datetime import date

@pytest.fixture
def user(db):
    user = User.objects.create_user(username='staff', password='password123')
    # Grant view_salesorder permission
    perm = Permission.objects.get(codename='view_salesorder')
    user.user_permissions.add(perm)
    return user

@pytest.fixture
def partner(db, user):
    return Partner.objects.create(name="Customer 1", code="CUST001", is_customer=True, created_by=user)

@pytest.mark.django_db
class TestSalesOverviewView:
    def test_unauthenticated_denied(self, client):
        url = reverse('sales:overview')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden due to raise_exception = True

    def test_missing_permission_denied(self, client):
        # Create user without view_salesorder permission
        u = User.objects.create_user(username='no-perm', password='password123')
        client.login(username='no-perm', password='password123')
        url = reverse('sales:overview')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_authorized_access_and_metrics(self, client, user, partner):
        client.login(username='staff', password='password123')
        url = reverse('sales:overview')

        # Create catalog item first
        from catalog.models import Item
        catalog_item = Item.objects.create(sku="SKU1", name="Item 1", created_by=user)

        # Create active sales orders of different statuses
        # Confirmed
        order_confirmed = SalesService.create_order(
            document_no="SO-CONF",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        SalesService.add_item(order_confirmed, item=catalog_item, requested_qty=10, unit_price=10.00)
        order_confirmed.status = SalesOrder.Status.CONFIRMED
        order_confirmed.save()

        # Preorder
        order_preorder = SalesService.create_order(
            document_no="SO-PRE",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.PREORDER
        )
        SalesService.add_item(order_preorder, item=catalog_item, requested_qty=5, unit_price=20.00) # 100.00
        order_preorder.status = SalesOrder.Status.PREORDER
        order_preorder.save()

        # Draft
        order_draft = SalesService.create_order(
            document_no="SO-DRAFT",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        SalesService.add_item(order_draft, item=catalog_item, requested_qty=2, unit_price=15.00) # 30.00
        order_draft.status = SalesOrder.Status.DRAFT
        order_draft.save()

        # Cancelled
        order_cancelled = SalesService.create_order(
            document_no="SO-CANCEL",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        # Add manually to cancelled order
        SalesOrderItem.objects.create(order=order_cancelled, item=catalog_item, requested_qty=1, unit_price=50.00)
        order_cancelled.status = SalesOrder.Status.CANCELLED
        order_cancelled.save()

        # Soft-deleted order (should NOT count anywhere)
        order_deleted = SalesService.create_order(
            document_no="SO-DELETED",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        # Add manually to deleted order
        SalesOrderItem.objects.create(order=order_deleted, item=catalog_item, requested_qty=10, unit_price=100.00)
        order_deleted.status = SalesOrder.Status.CONFIRMED
        order_deleted.is_deleted = True
        order_deleted.save()

        response = client.get(url)
        assert response.status_code == 200
        assert response.context['page_title'] == "Sales Overview"
        assert response.context['confirmed_count'] == 1
        assert response.context['preorder_count'] == 1
        assert response.context['draft_count'] == 1
        
        # total active revenue = 100 (confirmed) + 100 (preorder) + 30 (draft) + 50 (cancelled) = 280
        assert float(response.context['total_revenue']) == 280.0
        assert b"Sales Overview" in response.content


@pytest.mark.django_db
class TestSalesOrderListView:
    def test_unauthenticated_denied(self, client):
        url = reverse('sales:sales-order-list')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden due to raise_exception = True

    def test_missing_permission_denied(self, client):
        u = User.objects.create_user(username='no-perm', password='password123')
        client.login(username='no-perm', password='password123')
        url = reverse('sales:sales-order-list')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_authorized_list_and_search(self, client, user, partner):
        client.login(username='staff', password='password123')
        url = reverse('sales:sales-order-list')

        # Create partner 2 for specific search
        partner2 = Partner.objects.create(name="Acme Corp", code="CUST002", is_customer=True, created_by=user)

        # Create sales orders
        order1 = SalesService.create_order(document_no="SO-9001", partner=partner, user=user)
        order2 = SalesService.create_order(document_no="SO-9002", partner=partner2, user=user)
        
        # Soft-deleted order (should NOT appear)
        order_del = SalesService.create_order(document_no="SO-DEL", partner=partner, user=user)
        order_del.is_deleted = True
        order_del.save()

        # Verify default list
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['sales_orders']) == 2
        
        # Search by Document No
        response_search_doc = client.get(url, {'q': '9001'})
        assert len(response_search_doc.context['sales_orders']) == 1
        assert response_search_doc.context['sales_orders'][0].document_no == "SO-9001"

        # Search by Customer Name
        response_search_cust = client.get(url, {'q': 'Acme'})
        assert len(response_search_cust.context['sales_orders']) == 1
        assert response_search_cust.context['sales_orders'][0].document_no == "SO-9002"

        # Search with no matches
        response_no_match = client.get(url, {'q': 'NonExistent'})
        assert len(response_no_match.context['sales_orders']) == 0


@pytest.mark.django_db
class TestSalesOrderCreateView:
    def test_unauthenticated_denied(self, client):
        url = reverse('sales:sales-order-create')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden due to raise_exception = True

    def test_missing_permission_denied(self, client):
        u = User.objects.create_user(username='no-add-perm', password='password123')
        perm = Permission.objects.get(codename='view_salesorder')
        u.user_permissions.add(perm)
        client.login(username='no-add-perm', password='password123')
        url = reverse('sales:sales-order-create')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_get_creation_form(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item
        item = Item.objects.create(sku="ITEM-A", name="Item A", created_by=user, status='active')

        url = reverse('sales:sales-order-create')
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['page_title'] == "New Sales Order"
        assert 'suggested_no' in response.context
        assert partner in response.context['customers']
        assert any(it['id'] == item.id for it in response.context['items_list'])
        assert b"New Sales Order" in response.content

    def test_get_form_with_lots_and_reservations(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item
        from inventory.models import Warehouse, Stock, StockReservation

        item = Item.objects.create(sku="ITEM-B", name="Item B", created_by=user, status='active')
        wh = Warehouse.objects.create(name="Main WH", code="MWH", created_by=user)

        stock = Stock.objects.create(
            warehouse=wh,
            item=item,
            lot_number="LOT-001",
            balance=100.00,
            reserved_qty=0.00,
            created_by=user
        )

        res = StockReservation.objects.create(
            stock=stock,
            quantity=25.00,
            reference_no="RES-123",
            reference_type=StockReservation.ReferenceType.HOLD,
            created_by=user
        )
        stock.reserved_qty = 25.00
        stock.save()

        url = reverse('sales:sales-order-create')
        response = client.get(url)
        assert response.status_code == 200

        items_list = response.context['items_list']
        b_item = next(it for it in items_list if it['id'] == item.id)
        assert b_item['total_balance'] == 100.0
        assert b_item['total_reserved'] == 25.0
        assert b_item['total_available'] == 75.0

        assert len(b_item['lots']) == 1
        lot = b_item['lots'][0]
        assert lot['lot_number'] == "LOT-001"
        assert lot['balance'] == 100.0
        assert lot['reserved_qty'] == 25.0
        assert lot['available_qty'] == 75.0

        assert len(lot['reservations']) == 1
        r = lot['reservations'][0]
        assert r['reference_no'] == "RES-123"
        assert r['quantity'] == 25.0

    def test_post_creation_success(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item
        item = Item.objects.create(sku="ITEM-C", name="Item C", created_by=user, status='active')

        import json
        cart_data = [
            {
                'item_id': item.id,
                'requested_qty': 10.0,
                'unit_price': 15.5
            }
        ]

        url = reverse('sales:sales-order-create')
        post_data = {
            'partner': partner.id,
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': 'SO-T-1234',
            'note': 'This is a test sales order note.',
            'items_json': json.dumps(cart_data)
        }

        response = client.post(url, post_data)
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-list')

        so = SalesOrder.objects.get(document_no='SO-T-1234')
        assert so.partner == partner
        assert so.order_type == SalesOrder.OrderType.NORMAL
        assert so.note == 'This is a test sales order note.'
        assert so.created_by == user
        assert so.order_date == date(2026, 5, 22)

        items = so.items.all()
        assert len(items) == 1
        item_line = items[0]
        assert item_line.item == item
        assert float(item_line.requested_qty) == 10.0
        assert float(item_line.unit_price) == 15.5

    def test_post_creation_invalid_missing_fields(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        url = reverse('sales:sales-order-create')

        post_data = {
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': 'SO-T-EMPTY',
            'items_json': '[]'
        }
        response = client.post(url, post_data)
        assert response.status_code == 200
        assert b"Customer (Partner) is required." in response.content

    def test_post_creation_invalid_cart(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        url = reverse('sales:sales-order-create')

        post_data = {
            'partner': partner.id,
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': 'SO-T-BAD-JSON',
            'items_json': 'invalid-json'
        }
        response = client.post(url, post_data)
        assert response.status_code == 200
        assert b"Shopping cart data format is invalid." in response.content

    def test_post_creation_invalid_numeric_values(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item
        item = Item.objects.create(sku="ITEM-D", name="Item D", created_by=user, status='active')

        url = reverse('sales:sales-order-create')

        import json
        cart_data = [{'item_id': item.id, 'requested_qty': -5, 'unit_price': 10.0}]
        post_data = {
            'partner': partner.id,
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': 'SO-T-NEG',
            'items_json': json.dumps(cart_data)
        }
        response = client.post(url, post_data)
        assert response.status_code == 200
        assert b"Quantity must be greater than zero." in response.content

    def test_post_creation_duplicate_document_no(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item
        item = Item.objects.create(sku="ITEM-E", name="Item E", created_by=user, status='active')

        existing_so = SalesService.create_order(
            document_no="SO-DUP",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )

        url = reverse('sales:sales-order-create')
        import json
        cart_data = [{'item_id': item.id, 'requested_qty': 1, 'unit_price': 10.0}]
        post_data = {
            'partner': partner.id,
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': "SO-DUP",
            'items_json': json.dumps(cart_data)
        }
        response = client.post(url, post_data)
        assert response.status_code == 200
        assert b"already exists" in response.content

    def test_post_creation_with_item_packaging_conversion(self, client, user, partner):
        perm = Permission.objects.get(codename='add_salesorder')
        user.user_permissions.add(perm)
        client.login(username='staff', password='password123')

        from catalog.models import Item, ItemPackaging
        item = Item.objects.create(sku="ITEM-PKG-TEST", name="Item with Pkg", created_by=user, status='active')
        pkg = ItemPackaging.objects.create(item=item, name="Box", quantity=12, created_by=user, status='active')

        # Verify packaging preloads in GET request
        url = reverse('sales:sales-order-create')
        response = client.get(url)
        assert response.status_code == 200
        assert b"Box" in response.content

        # Verify POST converts successfully (the converted client side payload is sent)
        import json
        cart_data = [
            {
                'item_id': item.id,
                'requested_qty': 24.0,  # 2 Boxes * 12 pcs
                'unit_price': 10.0      # $120.00 Box / 12 pcs
            }
        ]

        post_data = {
            'partner': partner.id,
            'order_type': SalesOrder.OrderType.NORMAL,
            'order_date': '2026-05-22',
            'document_no': 'SO-T-PKG',
            'note': 'Testing packaging conversion values.',
            'items_json': json.dumps(cart_data)
        }

        response = client.post(url, post_data)
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-list')

        so = SalesOrder.objects.get(document_no='SO-T-PKG')
        items = so.items.all()
        assert len(items) == 1
        item_line = items[0]
        assert item_line.item == item
        assert float(item_line.requested_qty) == 24.0
        assert float(item_line.unit_price) == 10.0

