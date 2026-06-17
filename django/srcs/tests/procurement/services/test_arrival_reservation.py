import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from procurement.models import Arrival, ArrivalItem, ArrivalReservation
from procurement.services import ArrivalReservationService
from catalog.models import Item, Category
from inventory.models import Warehouse
from partners.models import Partner

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="procurement_user", password="password")

@pytest.fixture
def arrival_setup(test_user, db):
    # Setup base data
    category = Category.objects.create(name="Test Category", created_by=test_user)
    item = Item.objects.create(
        sku="FUTURE-ITEM",
        name="Future Item",
        category=category,
        created_by=test_user
    )
    warehouse = Warehouse.objects.create(name="Main Warehouse", code="WH01", created_by=test_user)
    supplier = Partner.objects.create(name="Supplier A", code="SUPA", is_supplier=True, created_by=test_user)
    
    # Create Arrival
    arrival = Arrival.objects.create(
        document_no="ARR-2024-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date="2024-12-01",
        created_by=test_user
    )
    
    # Create Arrival Item with 100 expected units
    arr_item = ArrivalItem.objects.create(
        arrival=arrival,
        item=item,
        expected_qty=Decimal("100.00"),
        created_by=test_user
    )
    return arr_item

@pytest.mark.django_db
def test_successful_future_reservation(arrival_setup):
    """Test reserving valid future quantity updates arrival item correctly."""
    res = ArrivalReservationService.reserve_future(
        arrival_item=arrival_setup,
        quantity=Decimal("40.00"),
        reference_no="SO-101"
    )
    
    assert res.quantity == Decimal("40.00")
    assert res.reference_no == "SO-101"
    
    arrival_setup.refresh_from_db()
    assert arrival_setup.reserved_qty == Decimal("40.00")
    assert arrival_setup.available_qty == Decimal("60.00")

@pytest.mark.django_db
def test_insufficient_arrival_qty_fails(arrival_setup):
    """Test that reserving more than expected raises ValidationError."""
    # First reserve 70 units
    ArrivalReservationService.reserve_future(arrival_setup, Decimal("70.00"), "SO-101")
    
    # Try to reserve another 50 (Total 120 > 100)
    with pytest.raises(ValidationError):
        ArrivalReservationService.reserve_future(arrival_setup, Decimal("50.00"), "SO-102")

@pytest.mark.django_db
def test_update_future_reservation(arrival_setup):
    """Test increasing and decreasing a future reservation."""
    res = ArrivalReservationService.reserve_future(arrival_setup, Decimal("20.00"), "SO-101")
    
    # Increase to 60
    ArrivalReservationService.update_reservation(res, Decimal("60.00"))
    arrival_setup.refresh_from_db()
    assert arrival_setup.reserved_qty == Decimal("60.00")
    
    # Decrease to 15
    ArrivalReservationService.update_reservation(res, Decimal("15.00"))
    arrival_setup.refresh_from_db()
    assert arrival_setup.reserved_qty == Decimal("15.00")

@pytest.mark.django_db
def test_release_future_reservation(arrival_setup):
    """Test releasing a future reservation."""
    res = ArrivalReservationService.reserve_future(arrival_setup, Decimal("30.00"), "SO-101")
    
    ArrivalReservationService.release(res)
    
    arrival_setup.refresh_from_db()
    assert arrival_setup.reserved_qty == Decimal("0.00")
    assert ArrivalReservation.objects.filter(is_deleted=False).count() == 0

    # Verify status is CANCELLED on the soft-deleted reservation
    res.refresh_from_db()
    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.CANCELLED

@pytest.mark.django_db
def test_delete_by_reference_future(arrival_setup, test_user):
    """Test bulk deletion of future reservations."""
    # Create another arrival item record
    arrival2 = Arrival.objects.create(
        document_no="ARR-2024-002",
        partner=arrival_setup.arrival.partner,
        warehouse=arrival_setup.arrival.warehouse,
        expected_date="2024-12-15",
        created_by=test_user
    )
    arr_item2 = ArrivalItem.objects.create(
        arrival=arrival2,
        item=arrival_setup.item,
        expected_qty=Decimal("50.00"),
        created_by=test_user
    )
    
    ArrivalReservationService.reserve_future(arrival_setup, Decimal("10.00"), "SO-TOTAL")
    ArrivalReservationService.reserve_future(arr_item2, Decimal("20.00"), "SO-TOTAL")
    
    assert ArrivalReservation.objects.filter(reference_no="SO-TOTAL", is_deleted=False).count() == 2
    
    # Delete by reference and type
    ArrivalReservationService.delete_by_reference(
        "SO-TOTAL", 
        ArrivalReservation.ReferenceType.SALES_ORDER
    )
    
    arrival_setup.refresh_from_db()
    arr_item2.refresh_from_db()
    assert arrival_setup.reserved_qty == Decimal("0.00")
    assert arr_item2.reserved_qty == Decimal("0.00")
    assert ArrivalReservation.objects.filter(is_deleted=False).count() == 0

@pytest.mark.django_db
def test_reservation_soft_delete_changes_status_to_cancelled(arrival_setup, test_user):
    """Verify that soft-deleting a reservation automatically transitions status to CANCELLED."""
    res = ArrivalReservation.objects.create(
        arrival_item=arrival_setup,
        quantity=Decimal("10.00"),
        reference_no="SO-101",
        created_by=test_user
    )
    assert res.is_deleted is False
    assert res.status == ArrivalReservation.ReservationStatus.RESERVED

    res.delete(user=test_user)
    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.CANCELLED
    assert res.deleted_by == test_user

@pytest.mark.django_db
def test_reservation_save_with_cancelled_status_soft_deletes(arrival_setup, test_user):
    """Verify that explicitly saving a reservation with CANCELLED status soft-deletes it."""
    res = ArrivalReservation.objects.create(
        arrival_item=arrival_setup,
        quantity=Decimal("10.00"),
        reference_no="SO-101",
        created_by=test_user
    )
    res.status = ArrivalReservation.ReservationStatus.CANCELLED
    res.updated_by = test_user
    res.save()

    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.CANCELLED
    assert res.deleted_by == test_user

@pytest.mark.django_db
def test_reservation_save_with_is_deleted_true_forces_cancelled_status(arrival_setup, test_user):
    """Verify that explicitly saving a reservation with is_deleted=True forces status to CANCELLED."""
    res = ArrivalReservation.objects.create(
        arrival_item=arrival_setup,
        quantity=Decimal("10.00"),
        reference_no="SO-101",
        created_by=test_user
    )
    res.is_deleted = True
    res.updated_by = test_user
    res.save()

    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.CANCELLED
    assert res.deleted_by == test_user

@pytest.mark.django_db
def test_reservation_restore_resets_status_to_reserved(arrival_setup, test_user):
    """Verify that restoring a soft-deleted reservation sets status to RESERVED and is_deleted to False."""
    res = ArrivalReservation.objects.create(
        arrival_item=arrival_setup,
        quantity=Decimal("10.00"),
        reference_no="SO-101",
        created_by=test_user
    )
    res.delete(user=test_user)
    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.CANCELLED

    res.restore()
    assert res.is_deleted is False
    assert res.status == ArrivalReservation.ReservationStatus.RESERVED
    assert res.deleted_by is None
    assert res.deleted_at is None

@pytest.mark.django_db
def test_reservation_restore_preserves_promoted_status(arrival_setup, test_user):
    """Verify that restoring a soft-deleted reservation that was in PROMOTED status preserves PROMOTED status."""
    res = ArrivalReservation.objects.create(
        arrival_item=arrival_setup,
        quantity=Decimal("10.00"),
        reference_no="SO-101",
        status=ArrivalReservation.ReservationStatus.PROMOTED,
        created_by=test_user
    )
    # Simulate pre-existing database record that has is_deleted=True and status=PROMOTED
    ArrivalReservation.objects.filter(pk=res.pk).update(is_deleted=True)
    res.refresh_from_db()
    assert res.is_deleted is True
    assert res.status == ArrivalReservation.ReservationStatus.PROMOTED

    res.restore()
    assert res.is_deleted is False
    assert res.status == ArrivalReservation.ReservationStatus.PROMOTED
    assert res.deleted_by is None
    assert res.deleted_at is None

