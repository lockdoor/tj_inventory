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
        assert order_item.allocations.filter(physical_reservation__stock=stock_a).exists()

        # 2. User manually picks Stock B
        SalesService.manual_allocate_stock(order_item, stock_b, 40)

        # 3. Verify
        # Total should be 100. 40 is manual (Stock B), 60 is auto (Stock A)
        assert order_item.allocations.count() == 2
        
        manual_alloc = order_item.allocations.get(is_manual=True)
        assert manual_alloc.physical_reservation.stock == stock_b
        assert manual_alloc.quantity == 40

        auto_alloc = order_item.allocations.get(is_manual=False)
        assert auto_alloc.physical_reservation.stock == stock_a
        assert auto_alloc.quantity == 60
