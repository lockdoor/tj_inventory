import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.utils import timezone
from partners.models import Partner
from catalog.models import Item, Category
from inventory.models import Warehouse, Stock, StockReservation
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from sales.services.sales_service import SalesService
from procurement.models import Arrival, ArrivalItem, ArrivalReservation
from procurement.services import ArrivalReservationService, ArrivalService
from inventory.services.movement_service import MovementService


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="procurement_user", password="password")


@pytest.mark.django_db
class TestArrivalReservationPromotion:

    @pytest.fixture(autouse=True)
    def setup_data(self, test_user):
        # 1. Setup category & catalog item
        self.category = Category.objects.create(name="Electronics", created_by=test_user)
        self.item = Item.objects.create(
            sku="PROMO-SKU",
            name="Promo Item",
            category=self.category,
            created_by=test_user
        )

        # 2. Setup Warehouse & Partners
        self.warehouse = Warehouse.objects.create(name="East Warehouse", code="WH-EAST", created_by=test_user)
        self.customer = Partner.objects.create(name="Customer Corp", code="CUST-01", is_customer=True, created_by=test_user)
        self.supplier = Partner.objects.create(name="Supplier Corp", code="SUPP-01", is_supplier=True, created_by=test_user)

        # 3. Create active scheduled Arrival with expected items
        self.arrival = Arrival.objects.create(
            document_no="ARR-PROMO",
            partner=self.supplier,
            warehouse=self.warehouse,
            expected_date=timezone.now().date(),
            status=Arrival.Status.SCHEDULED,
            created_by=test_user
        )
        self.arrival_item = ArrivalItem.objects.create(
            arrival=self.arrival,
            item=self.item,
            expected_qty=Decimal("15.00"),
            mfg_date=timezone.now().date(),
            exp_date=timezone.now().date() + timezone.timedelta(days=365),
            created_by=test_user
        )

    def test_successful_arrival_receipt_promotes_reservation(self, test_user):
        """
        Verify that completing an inbound movement for an arrival with active pre-allocations:
        1. Promotes the ArrivalReservation to a physical StockReservation.
        2. Maintains direct Reference to the ultimate Sales Order.
        3. Establishes the origin_arrival_item lineage link correctly.
        4. Seamlessly converts the related SalesAllocation from ARRIVAL to STOCK.
        """
        # 1. Create a Sales Order (no physical stock available, but incoming scheduled arrival exists)
        order = SalesService.create_order(
            document_no="SO-PROMO-1001",
            partner=self.customer,
            user=test_user,
            order_date=timezone.now().date(),
            items=[{
                "item": self.item,
                "requested_qty": Decimal("10.00"),
                "unit_price": Decimal("250.00")
            }]
        )
        order_item = order.items.first()

        # Verify that the smart allocation engine automatically pre-allocated the arrival!
        allocations = list(order_item.allocations.all())
        assert len(allocations) == 1
        sales_alloc = allocations[0]
        assert sales_alloc.source_type == SalesAllocation.SourceType.ARRIVAL
        assert sales_alloc.arrival_reservation is not None
        arrival_lock = sales_alloc.arrival_reservation

        # Confirm pre-allocation status
        self.arrival_item.refresh_from_db()
        assert self.arrival_item.reserved_qty == Decimal("10.00")
        assert self.arrival_item.available_qty == Decimal("5.00")

        # 2. Receive the arrival (initiate receipt movement)
        from inventory.models import InventoryMovement
        movement = ArrivalService.initiate_receiving(self.arrival, user=test_user)
        assert movement.status == InventoryMovement.Status.DRAFT

        # 3. Complete the inbound inventory movement (Finalize arrival receiving)
        MovementService.complete_movement(movement, user=test_user)

        # 4. Verify Inbound receiving has finalized the arrival and promoted the pre-allocation
        self.arrival.refresh_from_db()
        assert self.arrival.status == Arrival.Status.RECEIVED

        self.arrival_item.refresh_from_db()
        assert self.arrival_item.received_qty == Decimal("15.00")

        # --- A. Verify ArrivalReservation is cleaned up (soft-deleted) ---
        assert not ArrivalReservation.objects.filter(pk=arrival_lock.pk, is_deleted=False).exists()

        # --- B. Verify a new physical StockReservation has been created ---
        # It must reference the ultimate parent Sales Order directly
        physical_reservations = StockReservation.objects.filter(
            reference_no=order.document_no,
            reference_type=StockReservation.ReferenceType.SALES_ORDER,
            is_deleted=False
        )
        assert physical_reservations.count() == 1
        phys_res = physical_reservations.first()
        assert phys_res.quantity == Decimal("10.00")
        assert phys_res.sales_item == order_item
        
        # --- C. Verify the origin_arrival_item lineage link is established ---
        assert phys_res.origin_arrival_item == self.arrival_item

        # --- D. Verify SalesAllocation has transitioned type and links ---
        sales_alloc.refresh_from_db()
        assert sales_alloc.source_type == SalesAllocation.SourceType.STOCK
        assert sales_alloc.physical_reservation == phys_res
        assert sales_alloc.arrival_reservation is None

        # --- E. Verify physical stock reserved quantity is synchronized ---
        stock = phys_res.stock
        assert stock.balance == Decimal("15.00")
        assert stock.reserved_qty == Decimal("10.00")
        assert stock.available_qty == Decimal("5.00")
