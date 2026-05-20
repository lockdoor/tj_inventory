import pytest
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from procurement.models import Arrival, ArrivalItem
from procurement.services import ArrivalService
from catalog.models import Item, Category
from inventory.models import Warehouse, InventoryMovement

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="arrival_mgr", password="password")

@pytest.fixture
def sample_arrival(test_user, db):
    category = Category.objects.create(name="Test Category", created_by=test_user)
    item = Item.objects.create(
        sku="ARR-ITEM-01",
        name="Arrival Item",
        category=category,
        created_by=test_user
    )
    warehouse = Warehouse.objects.create(name="Main Warehouse", code="WH01", created_by=test_user)
    from partners.models import Partner
    supplier = Partner.objects.create(name="Supplier A", code="SUPA", is_supplier=True, created_by=test_user)
    
    arrival = Arrival.objects.create(
        document_no="ARR-2026-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date="2026-06-01",
        created_by=test_user,
        status=Arrival.Status.SCHEDULED
    )
    
    ArrivalItem.objects.create(
        arrival=arrival,
        item=item,
        expected_qty=Decimal("100.00")
    )
    return arrival

@pytest.mark.django_db
class TestArrivalServiceReceivingFlow:
    def test_initiate_cancel_and_resume_receiving(self, sample_arrival, test_user):
        # 1. Initiate Receiving
        movement = ArrivalService.initiate_receiving(sample_arrival, test_user)
        assert sample_arrival.status == Arrival.Status.RECEIVING
        assert movement.document_no == f"RCV-{sample_arrival.document_no}"
        assert movement.status == InventoryMovement.Status.DRAFT
        assert movement.items.count() == 1
        assert not movement.is_deleted

        # 2. Cancel Receiving
        ArrivalService.cancel_receiving(sample_arrival, test_user)
        sample_arrival.refresh_from_db()
        movement.refresh_from_db()
        assert sample_arrival.status == Arrival.Status.SCHEDULED
        assert movement.is_deleted

        # 3. Cannot cancel an arrival that is not in RECEIVING status
        with pytest.raises(ValidationError):
            ArrivalService.cancel_receiving(sample_arrival, test_user)

        # 4. Resume Receiving (should restore the soft-deleted movement)
        movement_restored = ArrivalService.initiate_receiving(sample_arrival, test_user)
        sample_arrival.refresh_from_db()
        assert sample_arrival.status == Arrival.Status.RECEIVING
        assert movement_restored.id == movement.id
        assert not movement_restored.is_deleted
        assert movement_restored.items.count() == 1

    def test_receiving_flow_with_packaging(self, sample_arrival, test_user):
        from catalog.models import ItemPackaging
        from procurement.models import PurchaseOrder, PurchaseOrderItem
        
        # 1. Create packaging unit (Carton = 10 pcs)
        packaging = ItemPackaging.objects.create(
            item=sample_arrival.items.first().item,
            name="Carton",
            quantity=10,
            created_by=test_user
        )
        
        # 2. Create PO & PO item
        po = PurchaseOrder.objects.create(
            document_no="PO-PACK-001",
            partner=sample_arrival.partner,
            created_by=test_user
        )
        po_item = PurchaseOrderItem.objects.create(
            purchase_order=po,
            item=sample_arrival.items.first().item,
            packaging=packaging,
            order_qty=Decimal("5.00"),
            unit_cost=Decimal("100.00") # $100 per carton -> $10 per piece
        )
        
        # Update sample arrival item to use this packaging & PO item
        arrival_item = sample_arrival.items.first()
        arrival_item.packaging = packaging
        arrival_item.po_item = po_item
        arrival_item.expected_qty = Decimal("5.00") # 5 cartons expected
        arrival_item.save()
        
        # Update sample arrival to link to PO
        sample_arrival.purchase_order = po
        sample_arrival.save()
        
        # 3. Initiate Receiving
        movement = ArrivalService.initiate_receiving(sample_arrival, test_user)
        assert movement.items.count() == 1
        mov_item = movement.items.first()
        
        # The movement item quantity must be in pieces: 5 cartons * 10 pcs = 50 pcs
        assert mov_item.quantity == Decimal("50.00")
        
        # The movement item unit cost must be per piece: $100.00 / 10 = $10.00
        assert mov_item.unit_cost == Decimal("10.00")
        
        # 4. Finalize/Complete the movement
        from inventory.services.movement_service import MovementService
        # Let's say we receive 40 pieces instead of 50
        mov_item.quantity = Decimal("40.00")
        mov_item.save()
        
        MovementService.complete_movement(movement, user=test_user)
        
        # Re-run finalization
        arrival_item.refresh_from_db()
        
        # received_qty must be in package units: 40 pieces / 10 = 4.00 cartons
        assert arrival_item.received_qty == Decimal("4.00")

    def test_receiving_copies_mfg_and_exp_date(self, sample_arrival, test_user):
        import datetime
        arrival_item = sample_arrival.items.first()
        arrival_item.mfg_date = datetime.date(2026, 1, 1)
        arrival_item.exp_date = datetime.date(2027, 1, 1)
        arrival_item.save()

        movement = ArrivalService.initiate_receiving(sample_arrival, test_user)
        mov_item = movement.items.first()
        
        assert mov_item.mfg_date == datetime.date(2026, 1, 1)
        assert mov_item.exp_date == datetime.date(2027, 1, 1)

@pytest.mark.django_db
class TestArrivalServiceDelete:
    def test_delete_arrival_with_no_movements(self, sample_arrival, test_user):
        ArrivalService.delete(sample_arrival, user=test_user)
        sample_arrival.refresh_from_db()
        assert sample_arrival.is_deleted

    def test_delete_arrival_with_active_movement_fails(self, sample_arrival, test_user):
        ArrivalService.initiate_receiving(sample_arrival, test_user)
        
        with pytest.raises(ValidationError) as excinfo:
            ArrivalService.delete(sample_arrival, user=test_user)
        assert "active inventory movements" in str(excinfo.value)
        
        sample_arrival.refresh_from_db()
        assert not sample_arrival.is_deleted

    def test_delete_arrival_with_soft_deleted_movement(self, sample_arrival, test_user):
        movement = ArrivalService.initiate_receiving(sample_arrival, test_user)
        ArrivalService.cancel_receiving(sample_arrival, test_user)
        
        # Now movement is soft-deleted
        movement.refresh_from_db()
        assert movement.is_deleted
        
        ArrivalService.delete(sample_arrival, user=test_user)
        sample_arrival.refresh_from_db()
        assert sample_arrival.is_deleted
        
        # Movement should be hard-deleted
        from inventory.models import InventoryMovement
        assert not InventoryMovement.objects.filter(id=movement.id).exists()


