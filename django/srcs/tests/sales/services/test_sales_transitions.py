import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.utils import timezone
from partners.models import Partner
from catalog.models import Item
from inventory.models import Warehouse, Stock, StockReservation, InventoryMovement
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from sales.services.sales_service import SalesService
from inventory.services.movement_service import MovementService
from inventory.services.reservation_service import ReservationService

@pytest.mark.django_db
class TestSalesOrderWarehouseIntegration:

    @pytest.fixture(autouse=True)
    def setup_data(self):
        # 1. Create User
        self.user = User.objects.create_user(username="warehouse_user", password="password123")
        # Assign change permission
        change_order_perm = Permission.objects.get(codename="change_salesorder")
        add_mv_perm = Permission.objects.get(codename="add_inventorymovement")
        view_mv_perm = Permission.objects.get(codename="view_inventorymovement")
        self.user.user_permissions.add(change_order_perm, add_mv_perm, view_mv_perm)

        # 2. Create Partner
        self.partner = Partner.objects.create(
            code="CUST-001",
            name="Apex Corp",
            is_customer=True,
            created_by=self.user
        )

        # 3. Create Warehouse
        self.warehouse = Warehouse.objects.create(
            code="WH-MAIN",
            name="Main Warehouse",
            created_by=self.user
        )

        # 4. Create Item
        self.item = Item.objects.create(
            sku="ITEM-A",
            name="Widget A",
            created_by=self.user
        )

        # 5. Seed physical stock
        self.stock = Stock.objects.create(
            warehouse=self.warehouse,
            item=self.item,
            lot_number="LOT-001",
            balance=100.00,
            reserved_qty=0.00,
            created_by=self.user
        )

    def test_full_warehouse_release_and_fulfillment_cycle(self, client):
        client.login(username="warehouse_user", password="password123")

        # 1. Create Sales Order in Draft status
        order = SalesService.create_order(
            document_no="SO-2026-0001",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        assert order.status == SalesOrder.Status.DRAFT

        # 2. Confirm order (sourcing engine allocates stock)
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # Let's verify StockReservation exists
        reservations = StockReservation.objects.filter(reference_no=order.document_no)
        assert reservations.count() == 1
        res = reservations.first()
        assert res.quantity == 10.00
        assert res.stock == self.stock

        # Ensure stock reservation registers
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00
        assert self.stock.available_qty == 90.00

        # 3. POST to Release View
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        response = client.post(release_url)
        assert response.status_code == 302 # Redirect to detail view

        # 4. Verify Order transitions to PROCESSING
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PROCESSING

        # 5. Verify Draft Outbound InventoryMovement created automatically
        movements = InventoryMovement.objects.filter(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER
        )
        assert movements.count() == 1
        movement = movements.first()
        assert movement.status == InventoryMovement.Status.DRAFT
        assert movement.type == InventoryMovement.MovementType.OUTBOUND
        assert movement.warehouse == self.warehouse

        # Verify movement items correspond to reservations
        mv_items = movement.items.all()
        assert mv_items.count() == 1
        mv_item = mv_items.first()
        assert mv_item.item == self.item
        assert mv_item.quantity == 10.00
        assert mv_item.lot_number == "LOT-001"

        # Verification that StockReservation is STILL active during PROCESSING phase
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()

        # 6. Complete the Inventory Movement
        MovementService.complete_movement(movement, user=self.user)

        # 7. Assert that completing the movement:
        # A. Decrements physical stock balance
        self.stock.refresh_from_db()
        assert self.stock.balance == 90.00
        assert self.stock.reserved_qty == 0.00

        # B. Releases StockReservations
        assert not StockReservation.objects.filter(reference_no=order.document_no).exists()

        # C. Transitions Sales Order status to SHIPPED
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.SHIPPED
        # Check item line is marked as SHIPPED
        order_item = order.items.first()
        assert order_item.fulfilled_qty == 10.00
        assert order_item.status == SalesOrderItem.Status.SHIPPED

        # 8. Revert completed movement back to DRAFT
        MovementService.revert_to_draft(movement, user=self.user)

        # 9. Assert that reverting:
        # A. Restores physical stock balance
        self.stock.refresh_from_db()
        assert self.stock.balance == 100.00
        assert self.stock.reserved_qty == 10.00

        # B. Re-creates StockReservation
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()

        # C. Demotes Sales Order status back to PROCESSING
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PROCESSING
        order_item.refresh_from_db()
        assert order_item.fulfilled_qty == 0.00
        assert order_item.status == SalesOrderItem.Status.ALLOCATED

    def test_release_non_confirmed_order_fails(self, client):
        client.login(username="warehouse_user", password="password123")

        order = SalesService.create_order(
            document_no="SO-2026-0002",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        assert order.status == SalesOrder.Status.DRAFT

        # Attempt to release a DRAFT order
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        response = client.post(release_url)
        assert response.status_code == 302

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.DRAFT
        # Assert no movements created
        assert not InventoryMovement.objects.filter(reference_no=order.document_no).exists()

    def test_confirm_order_fully_allocated_becomes_confirmed(self, client):
        client.login(username="warehouse_user", password="password123")

        # Create draft order
        order = SalesService.create_order(
            document_no="SO-2026-0003",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        assert order.status == SalesOrder.Status.DRAFT

        # Fully allocate it manually or let auto-allocation run on refresh
        confirm_url = reverse("sales:sales-order-confirm", kwargs={"pk": order.pk})
        response = client.post(confirm_url)
        assert response.status_code == 302

        order.refresh_from_db()
        # Since physical stock (100) is greater than requested (10), it should be fully physical stock, hence CONFIRMED!
        assert order.status == SalesOrder.Status.CONFIRMED

    def test_confirm_order_with_shortage_becomes_preorder(self, client):
        client.login(username="warehouse_user", password="password123")

        # Create draft order requesting more than available physical stock (100)
        order = SalesService.create_order(
            document_no="SO-2026-0004",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 150.00,
                "unit_price": 5.00
            }]
        )
        assert order.status == SalesOrder.Status.DRAFT

        confirm_url = reverse("sales:sales-order-confirm", kwargs={"pk": order.pk})
        response = client.post(confirm_url)
        assert response.status_code == 302

        order.refresh_from_db()
        # Since there is shortage, it transitions to PREORDER
        assert order.status == SalesOrder.Status.PREORDER

    def test_refresh_allocations_promotes_preorder_to_confirmed(self, client):
        client.login(username="warehouse_user", password="password123")

        # Create order with shortage (150 requested, 100 available)
        order = SalesService.create_order(
            document_no="SO-2026-0005",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 150.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.PREORDER
        order.save()

        # Increase physical stock balance so the shortage can be fully covered by stock
        self.stock.refresh_from_db()
        self.stock.balance = 200.00
        self.stock.save()

        # Refresh allocations
        refresh_url = reverse("sales:sales-order-refresh-allocations", kwargs={"pk": order.pk})
        response = client.post(refresh_url)
        assert response.status_code == 302

        order.refresh_from_db()
        # The refresh should cover the shortage with the new stock, promoting status to CONFIRMED!
        assert order.status == SalesOrder.Status.CONFIRMED
