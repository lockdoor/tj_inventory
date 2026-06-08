import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Sum, F
from django.contrib.auth import get_user_model
from catalog.models import Item
from partners.models import Partner
from inventory.models import Stock, StockReservation, Warehouse
from procurement.models import Arrival, ArrivalItem, ArrivalReservation, Shortage
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from sales.services.sales_service import SalesService

User = get_user_model()

@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='password')

@pytest.fixture
def partner(db, user):
    return Partner.objects.create(name="Test Customer", code="CUST001", is_customer=True, created_by=user)

@pytest.fixture
def supplier(db, user):
    return Partner.objects.create(name="Test Supplier", code="SUPP001", is_supplier=True, created_by=user)

@pytest.fixture
def warehouse(db, user):
    return Warehouse.objects.create(code="WH1", name="Main Warehouse", created_by=user)

@pytest.fixture
def item(db, user):
    return Item.objects.create(sku="TEST-SKU", name="Test Item", created_by=user)

mark_db = pytest.mark.django_db

@mark_db
class TestSalesServiceAllocation:

    def test_waterfall_priority_stock(self, item, partner, user, warehouse):
        """Test Step 2: Physical stock should be prioritized first."""
        # Create physical stock
        stock = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-001",
            balance=100,
            reserved_qty=0,
            created_by=user
        )

        # Create Sales Order for 50 units
        order = SalesService.create_order(
            document_no="SO-101",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 50, 'unit_price': 100}]
        )

        order_item = order.items.first()
        
        # Verify Allocation
        assert order_item.allocated_qty == 50
        assert order_item.status == SalesOrderItem.Status.ALLOCATED
        
        allocation = order_item.allocations.first()
        assert allocation.source_type == SalesAllocation.SourceType.STOCK
        assert allocation.quantity == 50
        assert allocation.physical_reservation.quantity == 50
        
        # Verify Stock Reserved Qty
        stock.refresh_from_db()
        assert stock.reserved_qty == 50

    def test_waterfall_priority_arrival(self, item, partner, user, supplier, warehouse):
        """Test Step 3: Arrivals should be picked if stock is empty."""
        # Create an Arrival scheduled for today
        arrival = Arrival.objects.create(
            document_no="ARR-001",
            partner=supplier,
            warehouse=warehouse,
            expected_date=date.today(),
            status='scheduled',
            created_by=user
        )
        arrival_item = ArrivalItem.objects.create(
            arrival=arrival,
            item=item,
            expected_qty=100,
        )

        # Create Sales Order
        order = SalesService.create_order(
            document_no="SO-102",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 30, 'unit_price': 100}]
        )

        order_item = order.items.first()
        assert order_item.status == SalesOrderItem.Status.ALLOCATED
        
        allocation = order_item.allocations.first()
        assert allocation.source_type == SalesAllocation.SourceType.ARRIVAL
        assert allocation.quantity == 30
        assert allocation.arrival_reservation.quantity == 30
        
        # Verify Arrival Reserved Qty
        arrival_item.refresh_from_db()
        assert arrival_item.reserved_qty == 30

    def test_waterfall_priority_shortage(self, item, partner, user):
        """Test Step 4: Shortage should be created if no stock or arrivals exist."""
        order = SalesService.create_order(
            document_no="SO-103",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 10, 'unit_price': 100}]
        )

        order_item = order.items.first()
        assert order_item.status == SalesOrderItem.Status.PENDING # No real stock
        
        allocation = order_item.allocations.first()
        assert allocation.source_type == SalesAllocation.SourceType.SHORTAGE
        assert allocation.quantity == 10
        assert allocation.shortage.request_qty == 10
        assert allocation.shortage.reference_id == "SO-103"

    def test_arrival_date_constraint(self, item, partner, user, supplier, warehouse):
        """Test that arrivals after the SO date are ignored."""
        # Arrival expected TOMORROW
        tomorrow = date.today() + timedelta(days=1)
        arrival = Arrival.objects.create(
            document_no="ARR-LATE",
            partner=supplier,
            warehouse=warehouse,
            expected_date=tomorrow,
            status='scheduled',
            created_by=user
        )
        ArrivalItem.objects.create(
            arrival=arrival,
            item=item,
            expected_qty=100
        )

        # Create Sales Order dated TODAY
        order = SalesService.create_order(
            document_no="SO-104",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 10, 'unit_price': 100}]
        )

        order_item = order.items.first()
        # Should be SHORTAGE because Arrival is tomorrow and Order is today
        allocation = order_item.allocations.first()
        assert allocation.source_type == SalesAllocation.SourceType.SHORTAGE

    def test_manual_allocation_preservation(self, item, partner, user, warehouse):
        """Test that manual picks are preserved during refresh."""
        stock_a = Stock.objects.create(item=item, warehouse=warehouse, lot_number="A", balance=100, created_by=user)
        stock_b = Stock.objects.create(item=item, warehouse=warehouse, lot_number="B", balance=100, created_by=user)

        order_item = SalesService.add_item(
            order=SalesService.create_order(document_no="SO-105", partner=partner, user=user, order_date=date.today()),
            item=item,
            requested_qty=100,
            unit_price=100
        )

        # 1. System auto-picks Stock A (FEFO)
        assert order_item.allocations.filter(physical_reservation__stock=stock_a, is_deleted=False).exists()

        # 2. User manually picks Stock B
        SalesService.manual_allocate_stock(order_item, stock_b, 40)

        # 3. Verify
        # Under new bypass rules: 40 is manual (Stock B), remaining 60 bypasses Stock A and goes straight to Shortage
        assert order_item.allocations.filter(is_deleted=False).count() == 2
        
        manual_alloc = order_item.allocations.get(is_manual=True, is_deleted=False)
        assert manual_alloc.physical_reservation.stock == stock_b
        assert manual_alloc.quantity == 40

        auto_alloc = order_item.allocations.get(is_manual=False, is_deleted=False)
        assert auto_alloc.source_type == SalesAllocation.SourceType.SHORTAGE
        assert auto_alloc.quantity == 60

    def test_save_manual_allocations_reuses_soft_deleted_records(self, item, partner, user, supplier, warehouse):
        """
        Verify that manual allocations reuse and restore soft-deleted allocations
        and reservations instead of creating duplicate database records.
        """
        # 1. Setup physical stock lot and arrival item
        stock = Stock.objects.create(
            item=item, warehouse=warehouse, lot_number="LOT-REUSE", balance=100, created_by=user
        )
        arrival = Arrival.objects.create(
            document_no="ARR-REUSE", partner=supplier, warehouse=warehouse, expected_date=date.today(), status='scheduled', created_by=user
        )
        arrival_item = ArrivalItem.objects.create(
            arrival=arrival, item=item, expected_qty=100
        )

        # 2. Create Sales Order
        order = SalesService.create_order(
            document_no="SO-REUSE",
            partner=partner,
            user=user,
            order_date=date.today()
        )
        order_item = SalesService.add_item(order, item=item, requested_qty=100, unit_price=10)

        # 3. Call save_manual_allocations with quantity 50 for both stock and arrival
        SalesService.save_manual_allocations(
            order_item=order_item,
            user=user,
            stock_qtys={stock.pk: 50},
            arrival_qtys={arrival_item.pk: 50}
        )

        # Verify initial active allocations and reservations
        active_allocs = list(order_item.allocations.filter(is_deleted=False))
        assert len(active_allocs) == 2
        
        stock_alloc = order_item.allocations.get(source_type=SalesAllocation.SourceType.STOCK, is_deleted=False)
        arrival_alloc = order_item.allocations.get(source_type=SalesAllocation.SourceType.ARRIVAL, is_deleted=False)
        
        assert stock_alloc.quantity == 50
        assert arrival_alloc.quantity == 50

        stock_res = stock_alloc.physical_reservation
        arrival_res = arrival_alloc.arrival_reservation

        assert stock_res.is_deleted is False
        assert stock_res.status == StockReservation.ReservationStatus.RESERVED
        assert stock_res.quantity == 50

        assert arrival_res.is_deleted is False
        assert arrival_res.quantity == 50

        # Save PKs for comparison
        stock_alloc_pk = stock_alloc.pk
        arrival_alloc_pk = arrival_alloc.pk
        stock_res_pk = stock_res.pk
        arrival_res_pk = arrival_res.pk

        # 4. Remove/release allocations (set submitted quantity to 0)
        SalesService.save_manual_allocations(
            order_item=order_item,
            user=user,
            stock_qtys={stock.pk: 0},
            arrival_qtys={arrival_item.pk: 0}
        )

        # Verify soft-deletion
        stock_alloc.refresh_from_db()
        arrival_alloc.refresh_from_db()
        stock_res.refresh_from_db()
        arrival_res.refresh_from_db()

        assert stock_alloc.is_deleted is True
        assert arrival_alloc.is_deleted is True
        assert stock_res.is_deleted is True
        assert stock_res.status == StockReservation.ReservationStatus.RELEASED
        assert arrival_res.is_deleted is True

        # 5. Re-allocate again using the same stock lot and arrival item with quantity 40 and 60
        SalesService.save_manual_allocations(
            order_item=order_item,
            user=user,
            stock_qtys={stock.pk: 40},
            arrival_qtys={arrival_item.pk: 60}
        )

        # Verify that the total counts (including soft-deleted) of allocations and reservations did not change
        assert order_item.allocations.count() == 3  # 2 active manual + 1 soft-deleted shortage
        assert StockReservation.objects.filter(sales_item=order_item).count() == 1  # Still only 1 reservation in total
        assert ArrivalReservation.objects.filter(sales_item=order_item).count() == 1

        # Retrieve the updated active allocations
        new_stock_alloc = order_item.allocations.get(source_type=SalesAllocation.SourceType.STOCK)
        new_arrival_alloc = order_item.allocations.get(source_type=SalesAllocation.SourceType.ARRIVAL)

        assert new_stock_alloc.is_deleted is False
        assert new_stock_alloc.quantity == 40
        assert new_stock_alloc.pk == stock_alloc_pk

        assert new_arrival_alloc.is_deleted is False
        assert new_arrival_alloc.quantity == 60
        assert new_arrival_alloc.pk == arrival_alloc_pk

        new_stock_res = new_stock_alloc.physical_reservation
        new_arrival_res = new_arrival_alloc.arrival_reservation

        assert new_stock_res.is_deleted is False
        assert new_stock_res.status == StockReservation.ReservationStatus.RESERVED
        assert new_stock_res.quantity == 40
        assert new_stock_res.pk == stock_res_pk

        assert new_arrival_res.is_deleted is False
        assert new_arrival_res.quantity == 60
        assert new_arrival_res.pk == arrival_res_pk

    def test_reset_allocations_reuses_soft_deleted_records(self, item, partner, user, warehouse):
        """
        Verify that calling reset_allocations restores and updates soft-deleted allocations
        and reservations when the auto-allocator falls back to the same source.
        """
        # 1. Setup physical stock lot
        stock = Stock.objects.create(
            item=item, warehouse=warehouse, lot_number="LOT-RESET-REUSE", balance=100, created_by=user
        )

        # 2. Create Sales Order
        order = SalesService.create_order(
            document_no="SO-RESET-REUSE",
            partner=partner,
            user=user,
            order_date=date.today()
        )
        order_item = SalesService.add_item(order, item=item, requested_qty=100, unit_price=10)

        # 3. Manually allocate the stock lot
        SalesService.save_manual_allocations(
            order_item=order_item,
            user=user,
            stock_qtys={stock.pk: 100},
            arrival_qtys={}
        )

        # Verify initial active manual allocation and reservation
        active_alloc = order_item.allocations.get(is_deleted=False)
        assert active_alloc.quantity == 100
        assert active_alloc.is_manual is True
        
        physical_res = active_alloc.physical_reservation
        assert physical_res.is_deleted is False
        assert physical_res.status == StockReservation.ReservationStatus.RESERVED

        # Save PKs for comparison
        alloc_pk = active_alloc.pk
        res_pk = physical_res.pk

        # 4. Call reset_allocations
        SalesService.reset_allocations(order_item, user)

        # Verify that the manual flag was unset
        order_item.refresh_from_db()
        assert order_item.is_manual_allocate is False

        # Verify that the allocation was restored and updated to is_manual = False, rather than a new one being created
        assert order_item.allocations.count() == 1  # Still exactly 1 record in the DB
        
        restored_alloc = order_item.allocations.get(is_deleted=False)
        assert restored_alloc.pk == alloc_pk
        assert restored_alloc.quantity == 100
        assert restored_alloc.is_manual is False

        restored_res = restored_alloc.physical_reservation
        assert restored_res.pk == res_pk
        assert restored_res.is_deleted is False
        assert restored_res.status == StockReservation.ReservationStatus.RESERVED
        assert restored_res.quantity == 100

    def test_update_order_preserves_manual_allocate_status(self, item, partner, user, warehouse):
        """
        Verify that updating an order preserves the is_manual_allocate flag on the items,
        ensuring that re-created lines are NOT automatically auto-allocated.
        """
        # 1. Setup physical stock lot
        stock = Stock.objects.create(
            item=item, warehouse=warehouse, lot_number="LOT-EDIT-TEST", balance=100, created_by=user
        )

        # 2. Create Sales Order
        order = SalesService.create_order(
            document_no="SO-EDIT-TEST",
            partner=partner,
            user=user,
            order_date=date.today()
        )
        order_item = SalesService.add_item(order, item=item, requested_qty=100, unit_price=10)

        # 3. Manually allocate the stock lot
        SalesService.save_manual_allocations(
            order_item=order_item,
            user=user,
            stock_qtys={stock.pk: 100},
            arrival_qtys={}
        )
        assert order_item.is_manual_allocate is True

        # 4. Update the order, e.g. changing note and quantity to 120
        updated_order = SalesService.update_order(
            order,
            document_no="SO-EDIT-TEST",
            partner=partner,
            user=user,
            order_date=date.today(),
            note="Updated Note",
            items=[{'item': item, 'requested_qty': 120, 'unit_price': 10}]
        )

        # Verify that the new item line is manual
        new_order_item = updated_order.items.first()
        assert new_order_item.is_manual_allocate is True

        # Verify that it bypassed stock auto-allocation and has no STOCK allocations (only shortage)
        active_allocs = list(new_order_item.allocations.filter(is_deleted=False))
        assert len(active_allocs) == 1
        assert active_allocs[0].source_type == SalesAllocation.SourceType.SHORTAGE
        assert active_allocs[0].quantity == 120

    def test_update_order_shortage_reused_in_place(self, item, partner, user):
        """
        Verify that updating an order with shortage does not create new shortage
        and sales allocation records, but updates the existing ones in-place.
        """
        from decimal import Decimal
        # 1. Create a Sales Order for 10 units of an item with no stock (causes shortage)
        order = SalesService.create_order(
            document_no="SO-SHORTAGE-EDIT",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 10, 'unit_price': 100}]
        )

        order_item = order.items.first()
        assert order_item.allocations.filter(is_deleted=False).count() == 1
        alloc = order_item.allocations.get(is_deleted=False)
        assert alloc.source_type == SalesAllocation.SourceType.SHORTAGE
        assert alloc.quantity == 10
        
        shortage = alloc.shortage
        assert shortage is not None
        assert shortage.request_qty == 10
        assert shortage.is_deleted is False

        # Save PKs for comparison
        alloc_pk = alloc.pk
        shortage_pk = shortage.pk

        # 2. Update the order, changing the requested quantity of the same item to 15
        updated_order = SalesService.update_order(
            order,
            document_no="SO-SHORTAGE-EDIT",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 15, 'unit_price': 100}]
        )

        # 3. Verify that the allocation and shortage were updated in-place (same PKs)
        new_order_item = updated_order.items.first()
        # The PK of the SalesOrderItem itself should also be preserved
        assert new_order_item.pk == order_item.pk
        
        new_alloc = new_order_item.allocations.get(is_deleted=False)
        assert new_alloc.pk == alloc_pk
        assert new_alloc.source_type == SalesAllocation.SourceType.SHORTAGE
        assert new_alloc.quantity == 15

        new_shortage = new_alloc.shortage
        assert new_shortage.pk == shortage_pk
        assert new_shortage.request_qty == 15
        assert new_shortage.is_deleted is False



@mark_db
class TestSalesOrderHardDeleteCleanup:

    def test_hard_delete_sales_order_releases_all_reservations_and_shortages(self, item, partner, user, supplier, warehouse):
        """
        Verify that hard-deleting a SalesOrder cleanly triggers the pre_delete signals
        to release/delete all associated StockReservations, ArrivalReservations, and Shortages.
        """
        # 1. Setup physical stock
        stock = Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-HD-001",
            balance=100,
            reserved_qty=0,
            created_by=user
        )

        # 2. Setup scheduled arrival
        arrival = Arrival.objects.create(
            document_no="ARR-HD-001",
            partner=supplier,
            warehouse=warehouse,
            expected_date=date.today(),
            status='scheduled',
            created_by=user
        )
        arrival_item = ArrivalItem.objects.create(
            arrival=arrival,
            item=item,
            expected_qty=100
        )

        # 3. Create a Sales Order that allocates from stock, arrival, and shortage
        # We need a requested qty of 250 (100 from stock, 100 from arrival, 50 shortage)
        order = SalesService.create_order(
            document_no="SO-HD-999",
            partner=partner,
            user=user,
            order_date=date.today(),
            items=[{'item': item, 'requested_qty': 250, 'unit_price': 100}]
        )

        order_item = order.items.first()
        
        # Verify allocations are active
        assert order_item.allocations.count() == 3
        
        # Verify Stock Reservation
        stock.refresh_from_db()
        assert stock.reserved_qty == 100
        
        # Verify Arrival Reservation
        arrival_item.refresh_from_db()
        assert arrival_item.reserved_qty == 100
        
        # Verify Shortage
        shortage_qs = Shortage.objects.filter(reference_id="SO-HD-999")
        assert shortage_qs.exists()
        assert shortage_qs.filter(is_deleted=False).count() == 1

        # 4. Now, HARD DELETE the SalesOrder (just like the user did in django shell)
        order.hard_delete()

        # 5. Assertions:
        # A. Stock reserved quantity must revert back to 0
        stock.refresh_from_db()
        assert stock.reserved_qty == 0

        # B. All StockReservations for this sales item must be marked as RELEASED and soft-deleted (is_deleted=True)
        res_qs = StockReservation.objects.filter(reference_no="SO-HD-999")
        for res in res_qs:
            assert res.status == StockReservation.ReservationStatus.RELEASED
            assert res.is_deleted is True

        # C. Arrival Item reserved quantity must revert back to 0
        arrival_item.refresh_from_db()
        assert arrival_item.reserved_qty == 0

        # D. All ArrivalReservations for this sales item must be soft-deleted
        assert not ArrivalReservation.objects.filter(reference_no="SO-HD-999", is_deleted=False).exists()

        # E. Shortages for this sales order must be soft-deleted
        assert not Shortage.objects.filter(reference_id="SO-HD-999", is_deleted=False).exists()
