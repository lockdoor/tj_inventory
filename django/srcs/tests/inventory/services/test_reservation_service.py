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
def test_successful_reservation(stock_setup):
    """Test reserving valid quantity updates stock correctly."""
    res = ReservationService.reserve(
        stock=stock_setup,
        quantity=Decimal("30.00"),
        reference_no="SO-001"
    )
    
    assert res.quantity == Decimal("30.00")
    assert res.reference_no == "SO-001"
    
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
def test_release_reservation(stock_setup):
    """Test releasing (deleting) a reservation."""
    res = ReservationService.reserve(stock_setup, Decimal("40.00"), "SO-001")
    
    ReservationService.release(res)
    
    stock_setup.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("0.00")
    assert StockReservation.objects.count() == 0

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
    
    assert StockReservation.objects.filter(reference_no="SO-999").count() == 2
    
    ReservationService.delete_by_reference("SO-999", StockReservation.ReferenceType.SALES_ORDER)
    
    stock_setup.refresh_from_db()
    stock2.refresh_from_db()
    assert stock_setup.reserved_qty == Decimal("0.00")
    assert stock2.reserved_qty == Decimal("0.00")
    assert StockReservation.objects.count() == 0
