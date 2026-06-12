import pytest
from decimal import Decimal
from datetime import date
from django.contrib.auth import get_user_model
from catalog.models import Item, Category
from partners.models import Partner
from inventory.models import Warehouse
from procurement.models import Arrival, ArrivalItem, ArrivalReservation, Shortage
from procurement.services.arrival_service import ArrivalService
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from sales.services.sales_service import SalesService

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="procurement_user", password="password")

@pytest.fixture
def supplier(db, test_user):
    return Partner.objects.create(name="Supplier A", code="SUPA", is_supplier=True, created_by=test_user)

@pytest.fixture
def customer(db, test_user):
    return Partner.objects.create(name="Customer A", code="CUSTA", is_customer=True, created_by=test_user)

@pytest.fixture
def warehouse(db, test_user):
    return Warehouse.objects.create(name="Main Warehouse", code="WH01", created_by=test_user)

@pytest.fixture
def item(db, test_user):
    category = Category.objects.create(name="Test Category", created_by=test_user)
    return Item.objects.create(sku="Sourcing-ITEM", name="Sourcing Item", category=category, created_by=test_user)

@pytest.mark.django_db
def test_full_shortage_promotion(item, customer, supplier, warehouse, test_user):
    """
    Verify that fully satisfying a shortage transitions it to PROMOTED status,
    links it to the created ArrivalReservation, and soft-deletes it.
    """
    # Create a Sales Order that creates a shortage
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('30.00'), 'unit_price': Decimal('10.00')}]
    )

    # Retrieve the shortage and verify initial state
    shortage = Shortage.objects.get(reference_id=str(so.id), is_deleted=False)
    assert shortage.status == Shortage.Status.PENDING

    # Promote to PO_CREATED to make it eligible for arrival allocation
    shortage.status = Shortage.Status.PO_CREATED
    shortage.save()

    # Create an Arrival matching the shortage qty
    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('30.00')}]
    )

    # Refresh shortage from DB (including soft-deleted records)
    shortage.refresh_from_db()
    assert shortage.is_deleted is True
    assert shortage.status == Shortage.Status.PROMOTED
    
    # Assert promoted_arrival_reservation is populated and matches the created ArrivalReservation
    assert shortage.promoted_arrival_reservation is not None
    arrival_res = shortage.promoted_arrival_reservation
    assert arrival_res.quantity == Decimal('30.00')
    assert arrival_res.arrival_item.arrival == arrival

    # Assert SalesAllocation has transitioned to ARRIVAL
    so_item = so.items.first()
    allocations = so_item.allocations.filter(is_deleted=False)
    assert allocations.count() == 1
    assert allocations[0].source_type == SalesAllocation.SourceType.ARRIVAL
    assert allocations[0].arrival_reservation == arrival_res
    assert allocations[0].shortage is None

    # Assert that the order is automatically promoted from DRAFT to PREORDER
    so.refresh_from_db()
    assert so.status == SalesOrder.Status.PREORDER

@pytest.mark.django_db
def test_partial_shortage_promotion_split(item, customer, supplier, warehouse, test_user):
    """
    Verify that a partially satisfied shortage is correctly split. The active portion
    should retain the remaining shortage quantity, and a new soft-deleted shortage
    with status PROMOTED should be created for the allocated portion.
    """
    # Create a Sales Order for 50 units
    so = SalesService.create_order(
        document_no="SO-002",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('50.00'), 'unit_price': Decimal('10.00')}]
    )

    # Retrieve and update shortage status to PO_CREATED
    shortage = Shortage.objects.get(reference_id=str(so.id), is_deleted=False)
    shortage.status = Shortage.Status.PO_CREATED
    shortage.save()

    # Create an Arrival for 20 units (leaving 30 units unallocated)
    arrival = ArrivalService.create(
        document_no="ARR-002",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('20.00')}]
    )

    # Assert the original shortage is still active and has request_qty = 30
    shortage.refresh_from_db()
    assert shortage.is_deleted is False
    assert shortage.status == Shortage.Status.PO_CREATED
    assert shortage.request_qty == Decimal('30.00')

    # Assert there is a promoted shortage with request_qty = 20 and is_deleted = True
    promoted_shortages = Shortage.objects.filter(
        reference_id=str(so.id),
        status=Shortage.Status.PROMOTED,
        is_deleted=True
    )
    assert promoted_shortages.count() == 1
    promoted_shortage = promoted_shortages.first()
    assert promoted_shortage.request_qty == Decimal('20.00')
    assert promoted_shortage.promoted_arrival_reservation is not None
    assert promoted_shortage.promoted_arrival_reservation.quantity == Decimal('20.00')
    assert promoted_shortage.promoted_arrival_reservation.arrival_item.arrival == arrival

    # Assert SalesAllocation is split into ARRIVAL (20) and SHORTAGE (30)
    so_item = so.items.first()
    allocations = so_item.allocations.filter(is_deleted=False).order_by('source_type')
    assert allocations.count() == 2
    
    assert allocations[0].source_type == SalesAllocation.SourceType.ARRIVAL
    assert allocations[0].quantity == Decimal('20.00')
    assert allocations[0].arrival_reservation == promoted_shortage.promoted_arrival_reservation
    
    assert allocations[1].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocations[1].quantity == Decimal('30.00')
    assert allocations[1].shortage == shortage

    # Assert that the order status remains DRAFT due to remaining shortages
    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT

@pytest.mark.django_db
def test_shortage_promotion_creator_attribution(item, customer, supplier, warehouse, test_user):
    """
    Verify that:
    1. Promoting a shortage to an arrival reservation preserves the shortage creator.
    2. Split promoted shortages preserve the shortage creator.
    3. Promoting an arrival reservation to a stock reservation preserves the arrival reservation creator.
    """
    # Create two different operators
    shortage_creator = User.objects.create_user(username="shortage_creator", password="password")
    arrival_creator = User.objects.create_user(username="arrival_creator", password="password")

    # Create Sales Order by shortage_creator
    so = SalesService.create_order(
        document_no="SO-PROM-USER",
        partner=customer,
        user=shortage_creator,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('100.00'), 'unit_price': Decimal('10.00')}]
    )

    # Verify that the shortage has shortage_creator as its creator
    shortage = Shortage.objects.get(reference_id=str(so.id), is_deleted=False)
    assert shortage.created_by == shortage_creator
    assert shortage.status == Shortage.Status.PENDING

    # Promote to PO_CREATED
    shortage.status = Shortage.Status.PO_CREATED
    shortage.save()

    # Create an Arrival for 40 units (partial allocation) by arrival_creator
    arrival = ArrivalService.create(
        document_no="ARR-PROM-USER",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=arrival_creator,
        items=[{'item': item, 'expected_qty': Decimal('40.00')}]
    )

    # Find the created ArrivalReservation
    arrival_res = ArrivalReservation.objects.get(reference_no=str(so.id), is_deleted=False)
    # 1. The arrival reservation must inherit the shortage's creator!
    assert arrival_res.created_by == shortage_creator

    # Find the split promoted shortage (soft-deleted)
    promoted_shortage = Shortage.objects.get(
        reference_id=str(so.id),
        status=Shortage.Status.PROMOTED,
        is_deleted=True
    )
    # 2. The split promoted shortage must inherit the shortage's creator!
    assert promoted_shortage.created_by == shortage_creator

    # 3. Now, finalize receiving of the arrival to promote arrival reservation to StockReservation
    from inventory.services.movement_service import MovementService
    from inventory.models import InventoryMovement
    
    # Initiate receiving using ArrivalService to ensure arrival_item links and quantities are correctly setup
    movement = ArrivalService.initiate_receiving(arrival, user=arrival_creator)

    # Complete movement properly via service
    MovementService.complete_movement(movement, user=arrival_creator)

    # Find the created StockReservation
    from inventory.models import StockReservation
    stock_res = StockReservation.objects.get(reference_no=str(so.id), is_deleted=False)

    # 4. The physical StockReservation must inherit the arrival reservation's creator (shortage_creator)!
    assert stock_res.created_by == shortage_creator

