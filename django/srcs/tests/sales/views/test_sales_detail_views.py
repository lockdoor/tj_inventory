import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from catalog.models import Item, Category
from partners.models import Partner
from inventory.models import Warehouse, Stock
from procurement.models import Arrival, ArrivalItem, Shortage


@pytest.mark.django_db
class TestSalesOrderDetailAndRefreshViews:
    """
    Test suite for SalesOrderDetailView and SalesOrderRefreshAllocationView.
    """

    @pytest.fixture
    def test_user(self):
        user = User.objects.create_user(username="authorized_user", password="password")
        # Grant view_salesorder and change_salesorder permissions
        perm_view = Permission.objects.get(codename="view_salesorder")
        perm_change = Permission.objects.get(codename="change_salesorder")
        user.user_permissions.add(perm_view, perm_change)
        return user

    @pytest.fixture
    def unauthorized_user(self):
        return User.objects.create_user(username="unauthorized_user", password="password")

    @pytest.fixture
    def category(self, test_user):
        return Category.objects.create(name="Spare Parts", code="SPARE", created_by=test_user)

    @pytest.fixture
    def item(self, test_user, category):
        return Item.objects.create(sku="SKU-TEST", name="Test Item", unit="pcs", category=category, created_by=test_user)

    @pytest.fixture
    def customer(self, test_user):
        return Partner.objects.create(name="Customer Corp", code="CUST01", is_customer=True, created_by=test_user)

    @pytest.fixture
    def warehouse(self, test_user):
        return Warehouse.objects.create(name="Main WH", code="WH-01", created_by=test_user)

    @pytest.fixture
    def sales_order(self, test_user, customer, item):
        from sales.services.sales_service import SalesService
        order = SalesService.create_order(
            document_no="SO-2026-999",
            partner=customer,
            user=test_user,
            order_type=SalesOrder.OrderType.NORMAL,
            items=[{
                'item': item,
                'requested_qty': Decimal("10.00"),
                'unit_price': Decimal("100.00")
            }]
        )
        return order

    def test_sales_order_detail_view_permissions(self, client, unauthorized_user, test_user, sales_order):
        url = reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # 1. Unauthenticated -> 403 Forbidden
        response = client.get(url)
        assert response.status_code == 403

        # 2. Authenticated but unauthorized -> 403 Forbidden
        client.force_login(unauthorized_user)
        response = client.get(url)
        assert response.status_code == 403

        # 3. Authorized -> 200 OK
        client.force_login(test_user)
        response = client.get(url)
        assert response.status_code == 200

    def test_sales_order_detail_view_content(self, client, test_user, sales_order, item):
        client.force_login(test_user)
        url = reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context['sales_order'] == sales_order
        assert response.context['total_amount'] == 1000.00  # 10.00 * 100.00
        assert response.context['total_items'] == 1

        # Initially, there is no stock so the smart allocator creates a shortage allocation
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.PENDING
        assert item_line.allocations.count() == 1
        alloc = item_line.allocations.first()
        assert alloc.source_type == SalesAllocation.SourceType.SHORTAGE
        assert alloc.quantity == Decimal("10.00")
        assert alloc.shortage is not None

    def test_refresh_allocations_view_post_success(self, client, test_user, sales_order, item, warehouse):
        # Create physical stock so we can fulfill the shortage gap upon refresh
        Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-AAA",
            balance=Decimal("20.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )

        client.force_login(test_user)
        
        # Verify there is a shortage allocation before refresh
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.PENDING
        assert item_line.allocations.filter(source_type=SalesAllocation.SourceType.SHORTAGE).exists()

        # Trigger POST refresh allocations
        url = reverse('sales:sales-order-refresh-allocations', kwargs={'pk': sales_order.pk})
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # Reload item line and verify allocations are refreshed to stock reservation
        item_line.refresh_from_db()
        assert item_line.status == SalesOrderItem.Status.ALLOCATED
        assert item_line.allocated_qty == Decimal("10.00")
        assert item_line.allocations.count() == 1
        
        alloc = item_line.allocations.first()
        assert alloc.source_type == SalesAllocation.SourceType.STOCK
        assert alloc.quantity == Decimal("10.00")
        assert alloc.physical_reservation is not None
        assert alloc.physical_reservation.stock.lot_number == "LOT-AAA"

    def test_refresh_allocations_view_post_blocked_cancelled(self, client, test_user, sales_order):
        # Cancel the sales order
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        client.force_login(test_user)
        url = reverse('sales:sales-order-refresh-allocations', kwargs={'pk': sales_order.pk})
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        
        # Verify no items were allocated
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.CANCELLED

    def test_manual_allocate_view_get(self, client, test_user, sales_order):
        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context['order_item'] == item_line
        assert response.context['order'] == sales_order
        assert 'stocks' in response.context
        assert 'arrival_items' in response.context

    def test_manual_allocate_view_post_success(self, client, test_user, sales_order, item, warehouse):
        # Create physical stock (exactly 6.00 so manual allocation uses all of it)
        stock = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-MANUAL",
            balance=Decimal("6.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )

        # Create incoming arrival
        supplier = Partner.objects.create(name="Supplier Corp", code="SUPP01", is_supplier=True, created_by=test_user)
        from django.utils import timezone
        arrival = Arrival.objects.create(
            document_no="ARR-2026-999",
            partner=supplier,
            warehouse=warehouse,
            expected_date=timezone.now().date(),
            status='scheduled',
            created_by=test_user
        )
        arrival_item = ArrivalItem.objects.create(
            arrival=arrival,
            item=item,
            expected_qty=Decimal("2.00"),
            reserved_qty=Decimal("0.00"),
        )

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})

        payload = {
            f"stock_qty_{stock.pk}": "6.00",
            f"arrival_qty_{arrival_item.pk}": "2.00",
        }
        response = client.post(url, data=payload)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # Reload allocations and assert manual picks and gap shortage are correct
        item_line.refresh_from_db()
        assert item_line.status == SalesOrderItem.Status.PARTIAL
        assert item_line.allocated_qty == Decimal("10.00") # 6 (stock) + 2 (arrival) + 2 (shortage)
        
        allocations = list(item_line.allocations.all().order_by('source_type'))
        assert len(allocations) == 3

        # Assert manual picks are registered as manual
        stock_alloc = item_line.allocations.get(source_type=SalesAllocation.SourceType.STOCK)
        assert stock_alloc.quantity == Decimal("6.00")
        assert stock_alloc.is_manual is True
        assert stock_alloc.physical_reservation.quantity == Decimal("6.00")

        arrival_alloc = item_line.allocations.get(source_type=SalesAllocation.SourceType.ARRIVAL)
        assert arrival_alloc.quantity == Decimal("2.00")
        assert arrival_alloc.is_manual is True
        assert arrival_alloc.arrival_reservation.quantity == Decimal("2.00")

        # Assert remaining gap is auto-sourced as a dynamic shortage (is_manual=False)
        shortage_alloc = item_line.allocations.get(source_type=SalesAllocation.SourceType.SHORTAGE)
        assert shortage_alloc.quantity == Decimal("2.00")
        assert shortage_alloc.is_manual is False
        assert shortage_alloc.shortage is not None

    def test_manual_allocate_view_post_blocked_cancelled(self, client, test_user, sales_order):
        from django.core.exceptions import ValidationError
        # Cancel order
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        
        with pytest.raises(ValidationError) as excinfo:
            client.post(url, data={})
        assert "Cannot manually allocate items for orders that are not in Draft status." in str(excinfo.value)

    def test_manual_allocate_view_get_blocked_cancelled(self, client, test_user, sales_order):
        from django.core.exceptions import ValidationError
        # Cancel order
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        
        with pytest.raises(ValidationError) as excinfo:
            client.get(url)
        assert "Cannot manually allocate items for orders that are not in Draft status." in str(excinfo.value)

    def test_reset_allocation_view_post_blocked_cancelled(self, client, test_user, sales_order):
        from django.core.exceptions import ValidationError
        # Cancel order
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-reset-allocation', kwargs={'item_pk': item_line.pk})
        
        with pytest.raises(ValidationError) as excinfo:
            client.post(url)
        assert "Cannot modify allocations for orders that are not in Draft status." in str(excinfo.value)

    def test_reset_allocation_view_post(self, client, test_user, sales_order, item, warehouse):
        # Setup manual reservations
        stock = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-RESET-TEST",
            balance=Decimal("20.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )
        item_line = sales_order.items.first()
        client.force_login(test_user)

        # Allocate manually first
        url_alloc = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        response = client.post(url_alloc, data={f"stock_qty_{stock.pk}": "5.00"})
        assert response.status_code == 302

        item_line.refresh_from_db()
        assert item_line.allocations.filter(is_manual=True).exists() is True

        # Now post to reset allocation
        url_reset = reverse('sales:sales-order-item-reset-allocation', kwargs={'item_pk': item_line.pk})
        response = client.post(url_reset)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        item_line.refresh_from_db()
        # All allocations should be reset to automatic (is_manual=False)
        for alloc in item_line.allocations.all():
            assert alloc.is_manual is False

    def test_manual_allocate_view_late_arrival_ignored_and_blocked(self, client, test_user, sales_order, item, warehouse):
        supplier = Partner.objects.create(name="Supplier Corp 2", code="SUPP02", is_supplier=True, created_by=test_user)
        from django.utils import timezone
        import datetime
        
        # 1. Create an on-time arrival (expected today)
        arrival_ontime = Arrival.objects.create(
            document_no="ARR-ONTIME",
            partner=supplier,
            warehouse=warehouse,
            expected_date=timezone.now().date(),
            status='scheduled',
            created_by=test_user
        )
        item_ontime = ArrivalItem.objects.create(
            arrival=arrival_ontime,
            item=item,
            expected_qty=Decimal("10.00"),
            reserved_qty=Decimal("0.00"),
        )

        # 2. Create a late arrival (expected in 5 days)
        arrival_late = Arrival.objects.create(
            document_no="ARR-LATE",
            partner=supplier,
            warehouse=warehouse,
            expected_date=timezone.now().date() + datetime.timedelta(days=5),
            status='scheduled',
            created_by=test_user
        )
        item_late = ArrivalItem.objects.create(
            arrival=arrival_late,
            item=item,
            expected_qty=Decimal("10.00"),
            reserved_qty=Decimal("0.00"),
        )

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})

        # Test GET: ARR-ONTIME should be in context, ARR-LATE should NOT
        response = client.get(url)
        assert response.status_code == 200
        arrival_items_in_context = list(response.context['arrival_items'])
        
        assert item_ontime in arrival_items_in_context
        assert item_late not in arrival_items_in_context

        # Test POST: submitting late arrival should throw validation error & display error flash message
        payload = {
            f"arrival_qty_{item_late.pk}": "5.00"
        }
        response = client.post(url, data=payload)
        assert response.status_code == 302 # Redirects to detail view on failure with flash error
        
        # Verify no allocations were registered (transaction rolled back)
        item_line.refresh_from_db()
        assert item_line.allocations.filter(source_type=SalesAllocation.SourceType.ARRIVAL).exists() is False

    def test_manual_allocate_view_get_releases_allocations(self, client, test_user, sales_order, item, warehouse):
        # Create some stock so we have active automatic allocations
        Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-GET-RELEASE",
            balance=Decimal("10.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )
        item_line = sales_order.items.first()
        from sales.services.sales_service import SalesService
        SalesService.refresh_allocation(item_line)

        # Assert we have active allocations before GET
        assert item_line.allocations.exists() is True

        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        response = client.get(url)
        assert response.status_code == 200

        # Assert GET successfully released and deleted all active allocations
        item_line.refresh_from_db()
        assert item_line.allocations.count() == 0

    def test_manual_allocate_view_cancel_rebuilds_auto(self, client, test_user, sales_order, item, warehouse):
        Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-CANCEL-REBUILD",
            balance=Decimal("10.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )
        item_line = sales_order.items.first()
        client.force_login(test_user)

        # Load GET (releases allocations)
        url_alloc = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        client.get(url_alloc)
        item_line.refresh_from_db()
        assert item_line.allocations.count() == 0

        # Cancel by calling the GET reset endpoint
        url_cancel = reverse('sales:sales-order-item-reset-allocation', kwargs={'item_pk': item_line.pk})
        response = client.get(url_cancel)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # Reload and assert allocations are rebuilt
        item_line.refresh_from_db()
        assert item_line.allocations.count() > 0
        assert item_line.allocations.filter(is_manual=False).exists() is True

    def test_smart_allocator_ignores_physical_stock_if_has_manual(self, client, test_user, sales_order, item, warehouse):
        # stock_A: exactly 3.00
        stock_A = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-A",
            balance=Decimal("3.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )
        # stock_B: 20.00 available
        stock_B = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-B",
            balance=Decimal("20.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )

        item_line = sales_order.items.first()
        client.force_login(test_user)

        # POST to allocate 3.00 manually from stock_A
        url_alloc = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})
        response = client.post(url_alloc, data={f"stock_qty_{stock_A.pk}": "3.00"})
        assert response.status_code == 302

        # Reload and assert manual allocation preserved, but auto-sourcing on stock_B was SKIPPED
        # Sourcing gap of 7.00 fell straight to dynamic shortage!
        item_line.refresh_from_db()
        
        allocations = list(item_line.allocations.all().order_by('source_type'))
        assert len(allocations) == 2

        # 1. Manual stock allocation from stock_A is kept
        stock_alloc = item_line.allocations.get(source_type=SalesAllocation.SourceType.STOCK)
        assert stock_alloc.quantity == Decimal("3.00")
        assert stock_alloc.is_manual is True
        assert stock_alloc.physical_reservation.stock == stock_A

        # 2. Dynamic shortage gap is logged for 7.00
        shortage_alloc = item_line.allocations.get(source_type=SalesAllocation.SourceType.SHORTAGE)
        assert shortage_alloc.quantity == Decimal("7.00")
        assert shortage_alloc.is_manual is False
        assert shortage_alloc.shortage is not None

        # 3. No physical allocation is present from stock_B (it was bypassed!)
        assert item_line.allocations.filter(physical_reservation__stock=stock_B).exists() is False

    def test_sales_order_edit_view_get_draft(self, client, test_user, sales_order):
        # By default sales_order status is 'draft' when created in create_order
        assert sales_order.status == SalesOrder.Status.DRAFT

        client.force_login(test_user)
        url = reverse('sales:sales-order-edit', kwargs={'pk': sales_order.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context['page_title'] == f"Edit Sales Order: {sales_order.document_no}"
        assert response.context['breadcrumb_title'] == "Edit Sales Order"
        assert response.context['submit_button_text'] == "Save Sales Order Changes"
        assert 'prepopulated_items_json' in response.context
        
        # Parse prepopulated cart items and verify matches
        import json
        prepopulated = json.loads(response.context['prepopulated_items_json'])
        assert len(prepopulated) == 1
        assert prepopulated[0]['item_id'] == sales_order.items.first().item.pk

    def test_sales_order_edit_view_get_non_draft_blocked(self, client, test_user, sales_order):
        # Cancel order so it's not draft
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        client.force_login(test_user)
        url = reverse('sales:sales-order-edit', kwargs={'pk': sales_order.pk})
        response = client.get(url)

        # Redirect to details page
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

    def test_sales_order_edit_view_post_success(self, client, test_user, sales_order, category):
        # Create second item and customer
        item2 = Item.objects.create(sku="SKU-2", name="Second Item", unit="pcs", category=category, created_by=test_user)
        customer2 = Partner.objects.create(name="Customer Corp 2", code="CUST02", is_customer=True, created_by=test_user)

        client.force_login(test_user)
        url = reverse('sales:sales-order-edit', kwargs={'pk': sales_order.pk})

        import json
        cart_payload = [
            {
                'item_id': item2.pk,
                'requested_qty': "5.00",
                'unit_price': "120.00"
            }
        ]
        
        payload = {
            'partner': customer2.pk,
            'order_type': SalesOrder.OrderType.PREORDER,
            'order_date': '2026-06-01',
            'document_no': 'SO-EDITED-NO',
            'note': 'This order has been successfully modified.',
            'items_json': json.dumps(cart_payload)
        }

        response = client.post(url, data=payload)
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # Reload sales order and assert new values
        sales_order.refresh_from_db()
        assert sales_order.document_no == 'SO-EDITED-NO'
        assert sales_order.partner == customer2
        assert sales_order.order_type == SalesOrder.OrderType.PREORDER
        assert sales_order.note == 'This order has been successfully modified.'
        
        # Verify old items deleted and new items created
        assert sales_order.items.count() == 1
        new_item_line = sales_order.items.first()
        assert new_item_line.item == item2
        assert new_item_line.requested_qty == Decimal("5.00")
        assert new_item_line.unit_price == Decimal("120.00")

    def test_manual_allocate_view_soft_deleted_arrival_ignored(self, client, test_user, sales_order, category, warehouse):
        # Fetch existing order item line
        item_line = sales_order.items.first()
        item = item_line.item

        # 1. Create a PO and a soft-deleted Arrival expected BEFORE the order expected date
        from procurement.models import PurchaseOrder, Arrival, ArrivalItem
        from datetime import date
        po = PurchaseOrder.objects.create(
            document_no="PO-DELETED-TEST",
            partner=sales_order.partner,
            expected_date=date(2026, 5, 20),
            created_by=test_user
        )
        deleted_arrival = Arrival.objects.create(
            document_no="ARR-DELETED-TEST",
            purchase_order=po,
            partner=sales_order.partner,
            warehouse=warehouse,
            expected_date=date(2026, 5, 20),
            status=Arrival.Status.SCHEDULED,
            is_deleted=True,  # SOFT-DELETED
            created_by=test_user
        )
        arrival_item = ArrivalItem.objects.create(
            arrival=deleted_arrival,
            item=item,
            expected_qty=Decimal("100.00")
        )

        client.force_login(test_user)
        url_alloc = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})

        # 2. Assert GET view ignores soft-deleted arrivals
        response = client.get(url_alloc)
        assert response.status_code == 200
        assert list(response.context['arrival_items']) == []  # Completely excluded!

        # 3. Assert POST view blocks manual reservations for soft-deleted arrivals (redirects gracefully with error)
        response = client.post(url_alloc, data={f"arrival_qty_{arrival_item.pk}": "5.00"})
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # 4. Assert smart allocation engine auto-sourcing also ignores soft-deleted arrivals
        # Reset allocations to force dynamic sourcing run
        from sales.services.sales_service import SalesService
        item_line.allocations.all().delete()
        SalesService.refresh_allocation(item_line)
        
        # Remaining gap must go to dynamic shortage, bypassing the deleted arrival!
        allocations = list(item_line.allocations.all())
        assert len(allocations) == 1
        assert allocations[0].source_type == SalesAllocation.SourceType.SHORTAGE
        assert allocations[0].quantity == item_line.requested_qty

    def test_manual_allocate_view_post_empty_forces_shortage(self, client, test_user, sales_order, item, warehouse):
        # Create physical stock so we can verify the auto-sourcing is bypassed
        stock = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-AUTO-TEST",
            balance=Decimal("10.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )

        item_line = sales_order.items.first()
        client.force_login(test_user)
        url = reverse('sales:sales-order-item-allocate', kwargs={'item_pk': item_line.pk})

        # POST an empty payload (neither stock nor arrival selected)
        payload = {}
        response = client.post(url, data=payload)
        assert response.status_code == 302

        # Reload item line and assert it's manual and has ONLY shortage allocations (bypassed physical stock completely!)
        item_line.refresh_from_db()
        assert item_line.is_manual_allocate is True
        assert item_line.status == SalesOrderItem.Status.PENDING  # 0 physical allocated

        allocations = list(item_line.allocations.all())
        assert len(allocations) == 1
        assert allocations[0].source_type == SalesAllocation.SourceType.SHORTAGE
        assert allocations[0].quantity == item_line.requested_qty
        assert allocations[0].is_manual is False
        assert allocations[0].shortage is not None
        sales_order.refresh_from_db()
        assert allocations[0].shortage.expected_date == sales_order.order_date

    def test_sales_order_attachment_upload_success(self, client, test_user, sales_order):
        from django.core.files.uploadedfile import SimpleUploadedFile
        client.force_login(test_user)
        url = reverse('sales:sales-order-attachment-upload', kwargs={'pk': sales_order.pk})
        
        document = SimpleUploadedFile("po_doc.pdf", b"pdf_content", content_type="application/pdf")
        response = client.post(url, data={
            'document_file': document,
            'note': 'Customer PO attachment note'
        })
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        
        # Verify saved attachment
        assert sales_order.attachments.count() == 1
        attachment = sales_order.attachments.first()
        assert attachment.file_name == 'po_doc.pdf'
        assert attachment.note == 'Customer PO attachment note'

    def test_sales_order_attachment_delete_success(self, client, test_user, sales_order):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from sales.models.attachment import SalesOrderAttachment
        
        # Pre-create attachment
        document = SimpleUploadedFile("to_delete.pdf", b"pdf_content", content_type="application/pdf")
        attachment = SalesOrderAttachment.objects.create(
            sales_order=sales_order,
            document_file=document,
            note='To be deleted remark',
            created_by=test_user
        )
        assert sales_order.attachments.count() == 1
        
        client.force_login(test_user)
        url = reverse('sales:sales-order-attachment-delete', kwargs={'pk': attachment.pk})
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        
        # Verify soft-deleted
        assert sales_order.attachments.filter(is_deleted=False).count() == 0




