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

    def test_confirm_order_with_shortage_remains_draft(self, client):
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
        # Since there is a shortage, it cannot be confirmed and remains in DRAFT
        assert order.status == SalesOrder.Status.DRAFT

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

    def test_discard_picking_slip_reverts_to_confirmed(self, client):
        client.login(username="warehouse_user", password="password123")

        # Give the user delete permission for inventory movement
        delete_mv_perm = Permission.objects.get(codename="delete_inventorymovement")
        self.user.user_permissions.add(delete_mv_perm)

        # 1. Create Sales Order and confirm it
        order = SalesService.create_order(
            document_no="SO-2026-0099",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # 2. Release to Warehouse (Order becomes PROCESSING, draft movement is generated)
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        client.post(release_url)
        
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PROCESSING

        # Fetch draft outbound movement
        movement = InventoryMovement.objects.get(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            is_deleted=False
        )
        assert movement.status == InventoryMovement.Status.DRAFT

        # 3. Post to the Movement Delete View with next/referer simulation
        delete_url = reverse("inventory:movement-delete", kwargs={"pk": movement.pk})
        response = client.post(delete_url, HTTP_REFERER=reverse("sales:sales-order-detail", kwargs={"pk": order.pk}))
        
        # Should redirect back to the sales order detail view because of referer
        assert response.status_code == 302
        assert response.url == reverse("sales:sales-order-detail", kwargs={"pk": order.pk})

        # 4. Verify draft movement is soft-deleted
        assert InventoryMovement.objects.filter(pk=movement.pk, is_deleted=True).exists()

        # 5. Verify Sales Order transitioned back to CONFIRMED
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.CONFIRMED

        # 6. Verify reservations are still active and preserved
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()

    def test_discard_picking_slip_by_warehouse_admin_group(self, client):
        # Create a new user with no delete permission, but put them in the 'warehouse_admin' group
        wh_admin_user = User.objects.create_user(username="wh_admin_group_user", password="password123")
        group, _ = Group.objects.get_or_create(name="warehouse_admin")
        wh_admin_user.groups.add(group)

        client.login(username="wh_admin_group_user", password="password123")

        # 1. Create Sales Order and confirm it using setup user
        order = SalesService.create_order(
            document_no="SO-2026-0098",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # 2. Release to Warehouse (Order becomes PROCESSING, draft movement is generated)
        # Note: self.user has change_salesorder and add_inventorymovement permissions.
        # We perform the release action by logging in as the setup user first
        client.login(username="warehouse_user", password="password123")
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        client.post(release_url)
        
        # Verify draft outbound movement
        movement = InventoryMovement.objects.get(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            is_deleted=False
        )
        assert movement.status == InventoryMovement.Status.DRAFT

        # Now login as wh_admin_group_user (no delete permission, but is in the group)
        client.login(username="wh_admin_group_user", password="password123")

        # 3. Post to the Movement Delete View
        delete_url = reverse("inventory:movement-delete", kwargs={"pk": movement.pk})
        response = client.post(delete_url, HTTP_REFERER=reverse("sales:sales-order-detail", kwargs={"pk": order.pk}))
        
        assert response.status_code == 302
        assert InventoryMovement.objects.filter(pk=movement.pk, is_deleted=True).exists()

    def test_discard_picking_slip_by_creator_user(self, client):
        # Create a new user who will create the sales order and release it
        creator_user = User.objects.create_user(username="creator_user", password="password123")
        # Give them change_salesorder and add_inventorymovement permission but NOT delete_inventorymovement
        change_order_perm = Permission.objects.get(codename="change_salesorder")
        add_mv_perm = Permission.objects.get(codename="add_inventorymovement")
        creator_user.user_permissions.add(change_order_perm, add_mv_perm)

        client.login(username="creator_user", password="password123")

        # 1. Create Sales Order and confirm it
        order = SalesService.create_order(
            document_no="SO-2026-0097",
            partner=self.partner,
            user=creator_user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # 2. Release to Warehouse (movement created by creator_user)
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        client.post(release_url)
        
        # Fetch draft outbound movement
        movement = InventoryMovement.objects.get(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            is_deleted=False
        )
        assert movement.status == InventoryMovement.Status.DRAFT
        assert movement.created_by == creator_user

        # 3. Post to the Movement Delete View (creator user has no delete_inventorymovement permission, but is the creator)
        delete_url = reverse("inventory:movement-delete", kwargs={"pk": movement.pk})
        response = client.post(delete_url, HTTP_REFERER=reverse("sales:sales-order-detail", kwargs={"pk": order.pk}))
        
        assert response.status_code == 302
        assert InventoryMovement.objects.filter(pk=movement.pk, is_deleted=True).exists()

    def test_discard_picking_slip_blocked_for_unauthorized_user(self, client):
        # Create a random user
        random_user = User.objects.create_user(username="random_user", password="password123")

        # 1. Create Sales Order and confirm it
        order = SalesService.create_order(
            document_no="SO-2026-0096",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # 2. Release to Warehouse
        client.login(username="warehouse_user", password="password123")
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        client.post(release_url)
        
        # Fetch draft outbound movement
        movement = InventoryMovement.objects.get(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            is_deleted=False
        )

        # Login as random_user
        client.login(username="random_user", password="password123")

        # 3. Attempt to post to the Movement Delete View
        delete_url = reverse("inventory:movement-delete", kwargs={"pk": movement.pk})
        response = client.post(delete_url, HTTP_REFERER=reverse("sales:sales-order-detail", kwargs={"pk": order.pk}))
        
        # Should be forbidden
        assert response.status_code in [403, 302]
        if response.status_code == 302:
            assert "login" in response.url
        assert not InventoryMovement.objects.get(pk=movement.pk).is_deleted

    def test_revert_confirmed_order_to_draft_releases_allocations(self, client):
        client.login(username="warehouse_user", password="password123")

        # 1. Create Sales Order and confirm it
        order = SalesService.create_order(
            document_no="SO-2026-0080",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # Confirm allocations and reservations exist
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00

        # 2. Revert the Sales Order to Draft
        revert_url = reverse("sales:sales-order-revert-to-draft", kwargs={"pk": order.pk})
        response = client.post(revert_url)
        assert response.status_code == 302
        assert response.url == reverse("sales:sales-order-detail", kwargs={"pk": order.pk})

        # 3. Assert status and allocations are preserved
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.DRAFT
        
        # Verify reservations preserved
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00

        # Verify items status remains ALLOCATED and fulfilled qty cleared, but allocated_qty preserved
        item = order.items.first()
        assert item.status == SalesOrderItem.Status.ALLOCATED
        assert item.fulfilled_qty == 0.00
        assert item.allocated_qty == 10.00

    def test_revert_preorder_order_to_draft_releases_shortages(self, client):
        client.login(username="warehouse_user", password="password123")

        # Create order with shortage (150 requested, 100 available)
        order = SalesService.create_order(
            document_no="SO-2026-0081",
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

        # Verify that active dynamic shortage exists
        from procurement.models import Shortage
        assert Shortage.objects.filter(reference_id=order.document_no, is_deleted=False).exists()

        # Revert to Draft
        revert_url = reverse("sales:sales-order-revert-to-draft", kwargs={"pk": order.pk})
        response = client.post(revert_url)
        assert response.status_code == 302

        # Assert status is draft and shortage is preserved
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.DRAFT
        assert Shortage.objects.filter(reference_id=order.document_no, is_deleted=False).exists()

    def test_revert_reverted_movement_order_to_draft_releases_reservations(self, client):
        client.login(username="warehouse_user", password="password123")

        # 1. Create Sales Order and confirm it
        order = SalesService.create_order(
            document_no="SO-2026-0082",
            partner=self.partner,
            user=self.user,
            items=[{
                "item": self.item,
                "requested_qty": 10.00,
                "unit_price": 5.00
            }]
        )
        order.status = SalesOrder.Status.CONFIRMED
        order.save()

        # 2. Release to Warehouse (Order becomes PROCESSING, draft movement is generated)
        release_url = reverse("sales:sales-order-release", kwargs={"pk": order.pk})
        client.post(release_url)

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PROCESSING

        # Fetch draft outbound movement
        movement = InventoryMovement.objects.get(
            reference_no=order.document_no,
            reference_type=InventoryMovement.ReferenceType.SALES_ORDER,
            is_deleted=False
        )
        assert movement.status == InventoryMovement.Status.DRAFT

        # 3. Complete the Outbound Movement (transitions order to SHIPPED and deletes the reservation hold)
        MovementService.complete_movement(movement, user=self.user)
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.SHIPPED
        assert not StockReservation.objects.filter(reference_no=order.document_no).exists()

        # 4. Revert the completed movement back to Draft (transitions order back to PROCESSING and restores the reservation)
        MovementService.revert_to_draft(movement, user=self.user)
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.PROCESSING
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()

        # Give the user delete permission for inventory movement
        delete_mv_perm = Permission.objects.get(codename="delete_inventorymovement")
        self.user.user_permissions.add(delete_mv_perm)

        # 4b. Discard the draft picking slip (Order transitions back to CONFIRMED)
        delete_url = reverse("inventory:movement-delete", kwargs={"pk": movement.pk})
        client.post(delete_url, HTTP_REFERER=reverse("sales:sales-order-detail", kwargs={"pk": order.pk}))
        
        order.refresh_from_db()
        assert order.status == SalesOrder.Status.CONFIRMED

        # 5. Revert the Sales Order to Draft (demotes order to DRAFT and should preserve allocations)
        revert_url = reverse("sales:sales-order-revert-to-draft", kwargs={"pk": order.pk})
        response = client.post(revert_url)
        assert response.status_code == 302

        order.refresh_from_db()
        assert order.status == SalesOrder.Status.DRAFT

        # 6. Verify restored reservations are successfully preserved
        assert StockReservation.objects.filter(reference_no=order.document_no).exists()
        self.stock.refresh_from_db()
        assert self.stock.reserved_qty == 10.00

        # Verify item attributes are preserved
        item = order.items.first()
        assert item.status == SalesOrderItem.Status.ALLOCATED
        assert item.fulfilled_qty == 0.00
        assert item.allocated_qty == 10.00




