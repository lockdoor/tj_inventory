import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from inventory.models import Warehouse, Stock, StockReservation
from inventory.services import ReservationService
from catalog.models import Item, Category

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="password")

@pytest.fixture
def stock_setup(test_user):
    category = Category.objects.create(name="Test Category", created_by=test_user)
    item = Item.objects.create(
        sku="TEST-ITEM",
        name="Test Item",
        category=category,
        created_by=test_user
    )
    warehouse = Warehouse.objects.create(name="Main Warehouse", code="WH01", created_by=test_user)
    
    stock = Stock.objects.create(
        warehouse=warehouse,
        item=item,
        lot_number="LOT-101",
        balance=Decimal("100.00"),
        reserved_qty=Decimal("0.00"),
        created_by=test_user
    )
    return stock

@pytest.mark.django_db
def test_successful_reservation(stock_setup, test_user):
    """Test reserving valid quantity updates stock correctly."""
    res = ReservationService.reserve(
        stock=stock_setup,
        quantity=Decimal("30.00"),
        reference_no="SO-001",
        created_by=test_user
    )
    
    assert res.quantity == Decimal("30.00")
    assert res.reference_no == "SO-001"
    assert res.status == StockReservation.ReservationStatus.RESERVED
    assert res.created_by == test_user
    assert res.is_deleted is False
    
    stock_setup.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("30.00")
    assert stock_setup.available_qty == Decimal("70.00")

@pytest.mark.django_db
def test_insufficient_stock_fails(stock_setup):
    """Test that reserving more than available raises ValidationError."""
    ReservationService.reserve(stock_setup, Decimal("80.00"), "SO-001")
    
    with pytest.raises(ValidationError):
        ReservationService.reserve(stock_setup, Decimal("30.00"), "SO-002")

@pytest.mark.django_db
def test_update_reservation_increase(stock_setup):
    """Test increasing an existing reservation."""
    res = ReservationService.reserve(stock_setup, Decimal("20.00"), "SO-001")
    
    ReservationService.update_reservation(res, Decimal("50.00"))
    
    stock_setup.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("50.00")

@pytest.mark.django_db
def test_update_reservation_insufficient(stock_setup):
    """Test increasing reservation beyond available stock fails."""
    res = ReservationService.reserve(stock_setup, Decimal("90.00"), "SO-001")
    
    with pytest.raises(ValidationError):
        ReservationService.update_reservation(res, Decimal("110.00"))

@pytest.mark.django_db
def test_release_reservation(stock_setup, test_user):
    """Test releasing (deleting) a reservation."""
    res = ReservationService.reserve(stock_setup, Decimal("40.00"), "SO-001", created_by=test_user)
    
    ReservationService.release(res, user=test_user)
    
    stock_setup.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("0.00")
    
    # Assert row is soft-deleted but preserved with status RELEASED
    assert StockReservation.objects.filter(is_deleted=False).count() == 0
    res.refresh_from_db()
    assert res.is_deleted is True
    assert res.status == StockReservation.ReservationStatus.RELEASED
    assert res.deleted_by == test_user

@pytest.mark.django_db
def test_delete_by_reference(stock_setup, test_user):
    """Test bulk deletion of reservations for a specific order."""
    # Create another stock record
    stock2 = Stock.objects.create(
        warehouse=stock_setup.warehouse,
        item=stock_setup.item,
        lot_number="LOT-102",
        balance=Decimal("50.00"),
        created_by=test_user
    )
    
    ReservationService.reserve(stock_setup, Decimal("10.00"), "SO-999")
    ReservationService.reserve(stock2, Decimal("20.00"), "SO-999")
    
    assert StockReservation.objects.filter(reference_no="SO-999", is_deleted=False).count() == 2
    
    ReservationService.delete_by_reference("SO-999", StockReservation.ReferenceType.SALES_ORDER, user=test_user)
    
    stock_setup.refresh_from_db()
    stock2.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("0.00")
    assert stock2.reserved_qty == Decimal("0.00")
    assert StockReservation.objects.filter(is_deleted=False).count() == 0
    
    # Assert historical audit rows
    for r in StockReservation.objects.filter(reference_no="SO-999"):
        assert r.is_deleted is True
        assert r.status == StockReservation.ReservationStatus.RELEASED
        assert r.deleted_by == test_user

@pytest.mark.django_db
def test_complete_reservation(stock_setup, test_user):
    """Test completing a reservation updates status and adjusts reserved stock quantity."""
    res = ReservationService.reserve(stock_setup, Decimal("30.00"), "SO-001", created_by=test_user)
    
    ReservationService.complete(res, user=test_user)
    
    # Assert row is kept, status completed, not soft-deleted
    res.refresh_from_db()
    assert res.is_deleted is False
    assert res.status == StockReservation.ReservationStatus.COMPLETED
    assert res.updated_by == test_user
    
    # Assert completed reservation no longer counts towards reserved quantity
    stock_setup.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("0.00")
    assert stock_setup.available_qty == Decimal("100.00")

@pytest.mark.django_db
def test_auditable_history_trail(stock_setup, test_user):
    """Test simple history tracks modifications to the reservation."""
    res = ReservationService.reserve(stock_setup, Decimal("25.00"), "SO-001", created_by=test_user)
    
    # Check that creation history was recorded
    assert res.history.count() == 1
    
    # Update quantity
    ReservationService.update_reservation(res, Decimal("40.00"), user=test_user)
    
    # Check history count incremented
    assert res.history.count() == 2
    
    # Validate old version quantity is preserved in history
    history_entries = list(res.history.all().order_by('history_date'))
    assert history_entries[0].quantity == Decimal("25.00")
    assert history_entries[1].quantity == Decimal("40.00")

