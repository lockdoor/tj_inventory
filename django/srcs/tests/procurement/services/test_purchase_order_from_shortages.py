import pytest
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from catalog.models import Item, Category
from partners.models import Partner
from procurement.models import PurchaseOrder, PurchaseOrderItem, Shortage
from procurement.services.purchase_order_service import PurchaseOrderService
from procurement.services.shortage_service import ShortageService

User = get_user_model()

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="procurement_officer", password="password")

@pytest.fixture
def supplier(db, test_user):
    return Partner.objects.create(name="Supplier B", code="SUPB", is_supplier=True, created_by=test_user)

@pytest.fixture
def item(db, test_user):
    category = Category.objects.create(name="Shortage Category", created_by=test_user)
    return Item.objects.create(sku="SHORT-ITEM-01", name="Shortage Item", category=category, created_by=test_user)

@pytest.mark.django_db
class TestPurchaseOrderFromShortages:
    def test_create_po_from_shortages_links_correctly(self, item, supplier, test_user):
        """
        Verify PO creation groups and links shortages correctly.
        """
        # 1. Create two pending shortages for the same item
        sh1 = ShortageService.create(
            item=item,
            request_qty=Decimal("10.00"),
            user=test_user,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-A",
            expected_date=date.today()
        )
        sh2 = ShortageService.create(
            item=item,
            request_qty=Decimal("5.00"),
            user=test_user,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-B",
            expected_date=date.today()
        )
        
        assert sh1.status == Shortage.Status.PENDING
        assert sh2.status == Shortage.Status.PENDING
        
        # 2. Create PO from shortages (covering them: total 15.00)
        items_payload = [{
            'item': item,
            'order_qty': Decimal("15.00"),
            'unit_cost': Decimal("20.00")
        }]
        
        po = PurchaseOrderService.create_from_shortages(
            document_no="PO-SHORTAGE-01",
            partner=supplier,
            user=test_user,
            expected_date=date.today(),
            items=items_payload,
            shortage_ids=[sh1.id, sh2.id]
        )
        
        assert po.status == PurchaseOrder.Status.DRAFT
        assert po.items.count() == 1
        po_item = po.items.first()
        assert po_item.item == item
        assert po_item.order_qty == Decimal("15.00")
        
        # Verify shortages are linked and marked as PO_CREATED
        sh1.refresh_from_db()
        sh2.refresh_from_db()
        assert sh1.status == Shortage.Status.PO_CREATED
        assert sh1.purchase_order == po
        assert sh2.status == Shortage.Status.PO_CREATED
        assert sh2.purchase_order == po

    def test_create_po_from_shortages_more_or_less_qty(self, item, supplier, test_user):
        """
        Verify user can order more or less than the shortages sum.
        """
        sh = ShortageService.create(
            item=item,
            request_qty=Decimal("10.00"),
            user=test_user,
            reference_type=Shortage.ReferenceType.OTHER,
            reference_id="REQ-01"
        )
        
        # Order more: 15.00 instead of 10.00
        po = PurchaseOrderService.create_from_shortages(
            document_no="PO-SHORTAGE-02",
            partner=supplier,
            user=test_user,
            expected_date=date.today(),
            items=[{
                'item': item,
                'order_qty': Decimal("15.00"),
                'unit_cost': Decimal("20.00")
            }],
            shortage_ids=[sh.id]
        )
        
        assert po.items.first().order_qty == Decimal("15.00")
        sh.refresh_from_db()
        assert sh.status == Shortage.Status.PO_CREATED
        assert sh.purchase_order == po

    def test_po_soft_delete_reverts_shortages(self, item, supplier, test_user):
        """
        Soft-deleting PO reverts linked shortages back to PENDING.
        """
        sh = ShortageService.create(
            item=item,
            request_qty=Decimal("10.00"),
            user=test_user,
            reference_type=Shortage.ReferenceType.OTHER
        )
        
        po = PurchaseOrderService.create_from_shortages(
            document_no="PO-SHORTAGE-03",
            partner=supplier,
            user=test_user,
            expected_date=date.today(),
            items=[{
                'item': item,
                'order_qty': Decimal("10.00"),
                'unit_cost': Decimal("20.00")
            }],
            shortage_ids=[sh.id]
        )
        
        sh.refresh_from_db()
        assert sh.status == Shortage.Status.PO_CREATED
        assert sh.purchase_order == po
        
        # Soft delete the PO
        PurchaseOrderService.soft_delete(po, user=test_user)
        
        sh.refresh_from_db()
        assert sh.status == Shortage.Status.PENDING
        assert sh.purchase_order is None

    def test_po_cancel_reverts_shortages(self, item, supplier, test_user):
        """
        Cancelling PO (transitioning status to CANCELLED) reverts shortages to PENDING.
        """
        sh = ShortageService.create(
            item=item,
            request_qty=Decimal("10.00"),
            user=test_user,
            reference_type=Shortage.ReferenceType.OTHER
        )
        
        po = PurchaseOrderService.create_from_shortages(
            document_no="PO-SHORTAGE-04",
            partner=supplier,
            user=test_user,
            expected_date=date.today(),
            items=[{
                'item': item,
                'order_qty': Decimal("10.00"),
                'unit_cost': Decimal("20.00")
            }],
            shortage_ids=[sh.id]
        )
        
        sh.refresh_from_db()
        assert sh.status == Shortage.Status.PO_CREATED
        
        # Transition status to CANCELLED
        PurchaseOrderService.update(po, user=test_user, status=PurchaseOrder.Status.CANCELLED)
        
        sh.refresh_from_db()
        assert sh.status == Shortage.Status.PENDING
        assert sh.purchase_order is None
