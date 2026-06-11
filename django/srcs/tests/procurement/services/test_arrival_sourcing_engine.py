import pytest
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from catalog.models import Item, Category
from partners.models import Partner
from inventory.models import Stock, StockReservation, Warehouse, InventoryMovement
from inventory.services.movement_service import MovementService
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
def test_auto_allocation_on_arrival_creation(item, customer, supplier, warehouse, test_user):
    """
    Verify that creating an arrival automatically allocates pending shortages in FIFO order.
    """
    # Create first Sales Order for 30 units
    so1 = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('30.00'), 'unit_price': Decimal('10.00')}]
    )

    # Create second Sales Order for 20 units
    so2 = SalesService.create_order(
        document_no="SO-002",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('20.00'), 'unit_price': Decimal('10.00')}]
    )

    # Verify shortages are created and ordered
    shortages = Shortage.objects.filter(item=item, status=Shortage.Status.PENDING).order_by('created_at')
    assert shortages.count() == 2
    assert shortages[0].reference_id == str(so1.id)
    assert shortages[1].reference_id == str(so2.id)

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    # Create Arrival with 40 units
    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('40.00')}]
    )

    # 30 units should go to SO-001 (fully satisfy)
    # 10 units should go to SO-002 (partially satisfy, leaving 10 shortage)
    
    # SO-001 assertions:
    assert not Shortage.objects.filter(reference_id=str(so1.id), is_deleted=False).exists()
    so1.refresh_from_db()
    assert so1.status == SalesOrder.Status.PREORDER

    so1_item = so1.items.first()
    so1_item.refresh_from_db()
    so1_allocs = so1_item.allocations.filter(is_deleted=False)
    assert so1_allocs.count() == 1
    assert so1_allocs[0].source_type == SalesAllocation.SourceType.ARRIVAL
    assert so1_allocs[0].quantity == Decimal('30.00')

    # SO-002 assertions:
    so2_shortages = Shortage.objects.filter(reference_id=str(so2.id), is_deleted=False)
    assert so2_shortages.count() == 1
    assert so2_shortages[0].request_qty == Decimal('10.00')
    so2.refresh_from_db()
    assert so2.status == SalesOrder.Status.DRAFT

    so2_item = so2.items.first()
    so2_item.refresh_from_db()
    so2_allocs = so2_item.allocations.filter(is_deleted=False).order_by('source_type')
    assert so2_allocs.count() == 2
    assert so2_allocs[0].source_type == SalesAllocation.SourceType.ARRIVAL
    assert os_alloc_qty(so2_allocs[0]) == Decimal('10.00')
    assert so2_allocs[1].source_type == SalesAllocation.SourceType.SHORTAGE
    assert os_alloc_qty(so2_allocs[1]) == Decimal('10.00')

    # ArrivalItem assertions:
    arr_item = arrival.items.first()
    arr_item.refresh_from_db()
    assert arr_item.reserved_qty == Decimal('40.00')


@pytest.mark.django_db
def test_auto_allocation_partial_split(item, customer, supplier, warehouse, test_user):
    """
    Verify that a single shortage is split correctly into arrival-allocated and shortage portions.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('50.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('20.00')}]
    )

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT  # Still outstanding shortage

    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False).order_by('source_type')
    assert allocs.count() == 2
    assert allocs[0].source_type == SalesAllocation.SourceType.ARRIVAL
    assert allocs[0].quantity == Decimal('20.00')
    assert allocs[1].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocs[1].quantity == Decimal('30.00')

    shortage = Shortage.objects.get(reference_id=str(so.id), is_deleted=False)
    assert shortage.request_qty == Decimal('30.00')


@pytest.mark.django_db
def test_revert_to_shortages_on_cancellation(item, customer, supplier, warehouse, test_user):
    """
    Verify that cancelling an arrival reverts the allocated reservations back to shortages and demotes the SalesOrder status.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.PREORDER

    # Cancel the arrival
    ArrivalService.update(arrival, user=test_user, status=Arrival.Status.CANCELLED)

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT

    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False)
    assert allocs.count() == 1
    assert allocs[0].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocs[0].quantity == Decimal('10.00')

    assert Shortage.objects.filter(reference_id=str(so.id), status=Shortage.Status.PENDING, is_deleted=False).exists()


@pytest.mark.django_db
def test_revert_to_shortages_on_deletion(item, customer, supplier, warehouse, test_user):
    """
    Verify that deleting an arrival reverts reservations back to pending shortages.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    # Delete arrival
    ArrivalService.delete(arrival, user=test_user)

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT

    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False)
    assert allocs.count() == 1
    assert allocs[0].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocs[0].quantity == Decimal('10.00')


@pytest.mark.django_db
def test_revert_remaining_on_short_receipt_close(item, customer, supplier, warehouse, test_user):
    """
    Verify that finalizing an under-received arrival reverts the unfulfilled expectations back to shortages.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.PREORDER

    # Initiate receiving
    movement = ArrivalService.initiate_receiving(arrival, user=test_user)
    
    # Simulate receiving only 6 units
    movement_item = movement.items.first()
    MovementService.update_item(movement_item, user=test_user, quantity=Decimal('6.00'))

    # Complete movement
    MovementService.complete_movement(movement, user=test_user)

    arrival.refresh_from_db()
    assert arrival.status == Arrival.Status.RECEIVED
    
    arr_item = arrival.items.first()
    assert arr_item.received_qty == Decimal('6.00')
    assert arr_item.reserved_qty == Decimal('0.00')
    # Verify physical stock reservation of 6 units
    assert StockReservation.objects.filter(origin_arrival_item=arr_item, is_deleted=False).count() == 1
    phys_res = StockReservation.objects.get(origin_arrival_item=arr_item, is_deleted=False)
    assert phys_res.quantity == Decimal('6.00')

    # Verify Sales Order status demoted to DRAFT
    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT

    # Verify allocations: 6 STOCK and 4 SHORTAGE
    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False).order_by('source_type')
    assert allocs.count() == 2
    assert allocs[0].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocs[0].quantity == Decimal('4.00')
    assert allocs[1].source_type == SalesAllocation.SourceType.STOCK
    assert allocs[1].quantity == Decimal('6.00')

    assert Shortage.objects.filter(reference_id=str(so.id), status=Shortage.Status.PENDING, is_deleted=False).exists()


@pytest.mark.django_db
def test_full_receipt_promotion(item, customer, supplier, warehouse, test_user):
    """
    Verify that fully receiving an arrival promotes arrival reservations to physical stock reservations
    and successfully promotes the SalesOrder status to CONFIRMED.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.PREORDER

    # Initiate receiving
    movement = ArrivalService.initiate_receiving(arrival, user=test_user)
    
    # Complete movement
    MovementService.complete_movement(movement, user=test_user)

    arrival.refresh_from_db()
    assert arrival.status == Arrival.Status.RECEIVED

    # Verify Sales Order is promoted to CONFIRMED
    so.refresh_from_db()
    assert so.status == SalesOrder.Status.CONFIRMED

    # Verify allocation is now STOCK
    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False)
    assert allocs.count() == 1
    assert allocs[0].source_type == SalesAllocation.SourceType.STOCK
    assert allocs[0].quantity == Decimal('10.00')


@pytest.mark.django_db
def test_block_reducing_expected_qty_below_reservations(item, customer, supplier, warehouse, test_user):
    """
    Verify that expected_qty on ArrivalItem cannot be reduced below reserved_qty.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    arr_item = arrival.items.first()
    assert arr_item.reserved_qty == Decimal('10.00')

    # Try to reduce expected_qty below reserved_qty
    arr_item.expected_qty = Decimal('5.00')
    with pytest.raises(ValidationError) as excinfo:
        arr_item.save()
    
    assert "Cannot reduce expected quantity below currently reserved quantity" in str(excinfo.value)


@pytest.mark.django_db
def test_revert_to_shortages_on_item_line_deletion(item, customer, supplier, warehouse, test_user):
    """
    Verify that deleting a specific ArrivalItem reverts its allocations to shortages.
    """
    so = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.PREORDER

    arr_item = arrival.items.first()
    assert arr_item.reserved_qty == Decimal('10.00')

    # Soft-delete the arrival item line
    arr_item.delete(user=test_user)

    so.refresh_from_db()
    assert so.status == SalesOrder.Status.DRAFT

    so_item = so.items.first()
    so_item.refresh_from_db()
    allocs = so_item.allocations.filter(is_deleted=False)
    assert allocs.count() == 1
    assert allocs[0].source_type == SalesAllocation.SourceType.SHORTAGE
    assert allocs[0].quantity == Decimal('10.00')

    assert Shortage.objects.filter(reference_id=str(so.id), status=Shortage.Status.PENDING, is_deleted=False).exists()


@pytest.mark.django_db
def test_auto_allocation_by_linked_purchase_order(item, customer, supplier, warehouse, test_user):
    """
    Verify that when an arrival is linked to a PO, it only allocates shortages linked to that same PO.
    """
    from procurement.models import PurchaseOrder

    # Create SO-001
    so1 = SalesService.create_order(
        document_no="SO-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )

    # Create SO-002
    so2 = SalesService.create_order(
        document_no="SO-002",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('10.00'), 'unit_price': Decimal('10.00')}]
    )

    # Create two different Purchase Orders
    po1 = PurchaseOrder.objects.create(
        document_no="PO-001",
        partner=supplier,
        expected_date=date.today(),
        created_by=test_user
    )
    po2 = PurchaseOrder.objects.create(
        document_no="PO-002",
        partner=supplier,
        expected_date=date.today(),
        created_by=test_user
    )

    # Link Shortage 1 to PO-001
    sh1 = Shortage.objects.get(reference_id=str(so1.id), is_deleted=False)
    sh1.purchase_order = po1
    sh1.status = Shortage.Status.PO_CREATED
    sh1.save()

    # Link Shortage 2 to PO-002
    sh2 = Shortage.objects.get(reference_id=str(so2.id), is_deleted=False)
    sh2.purchase_order = po2
    sh2.status = Shortage.Status.PO_CREATED
    sh2.save()

    # Create arrival linked to PO-001
    arrival = ArrivalService.create(
        document_no="ARR-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        purchase_order=po1,
        items=[{'item': item, 'expected_qty': Decimal('10.00')}]
    )

    # SO-001 should be allocated
    so1.refresh_from_db()
    assert so1.status == SalesOrder.Status.PREORDER
    so1_item = so1.items.first()
    so1_item.refresh_from_db()
    assert so1_item.allocations.filter(is_deleted=False, source_type=SalesAllocation.SourceType.ARRIVAL).count() == 1

    # SO-002 should NOT be allocated
    so2.refresh_from_db()
    assert so2.status == SalesOrder.Status.DRAFT
    so2_item = so2.items.first()
    so2_item.refresh_from_db()
    assert so2_item.allocations.filter(is_deleted=False, source_type=SalesAllocation.SourceType.SHORTAGE).count() == 1

    # Shortage 2 should still exist
    sh2.refresh_from_db()
    assert sh2.status == Shortage.Status.PO_CREATED


def os_alloc_qty(alloc):
    return alloc.quantity


@pytest.mark.django_db
def test_arrival_sourcing_packaging_units(item, customer, supplier, warehouse, test_user):
    """
    Verify expected_pieces and availability calculations when packaging is selected.
    """
    from catalog.models import ItemPackaging
    packaging = ItemPackaging.objects.create(
        item=item,
        name="Carton",
        quantity=12,
        created_by=test_user
    )

    # Create SO for 18 units (pieces)
    so = SalesService.create_order(
        document_no="SO-PKG-001",
        partner=customer,
        user=test_user,
        order_date=date.today(),
        items=[{'item': item, 'requested_qty': Decimal('18.00'), 'unit_price': Decimal('10.00')}]
    )
    # Simulate PO creation by updating shortage status to PO_CREATED

    # Simulate PO creation by updating shortage status to PO_CREATED
    Shortage.objects.filter(reference_id=str(so.id), is_deleted=False).update(status=Shortage.Status.PO_CREATED)

    # Create Arrival for 2 Cartons (which is 24 pieces)
    arrival = ArrivalService.create(
        document_no="ARR-PKG-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date=date.today(),
        user=test_user,
        items=[{
            'item': item,
            'expected_qty': Decimal('2.00'),
            'packaging': packaging
        }]
    )

    arr_item = arrival.items.first()
    # Check expected_pieces
    assert arr_item.expected_pieces == Decimal('24.00')
    # Check reserved_qty (18.00 pieces from SO)
    assert arr_item.reserved_qty == Decimal('18.00')
    # Check available_qty (24 - 18 = 6.00 pieces)
    assert arr_item.available_qty == Decimal('6.00')

    # Try to reduce expected_qty to 1 Carton (12 pieces).
    # Since 18 pieces are reserved, this should raise a ValidationError.
    arr_item.expected_qty = Decimal('1.00')
    with pytest.raises(ValidationError) as excinfo:
        arr_item.save()
    assert "Cannot reduce expected quantity below currently reserved quantity" in str(excinfo.value)
    
    # Try to reduce expected_qty to 1.5 Cartons (18 pieces).
    # This should be allowed because 18 pieces = 18 reserved.
    arr_item.expected_qty = Decimal('1.50')
    arr_item.save()
    assert arr_item.expected_pieces == Decimal('18.00')

