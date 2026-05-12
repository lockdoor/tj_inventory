import pytest
from django.contrib.auth import get_user_model
from procurement.services.purchase_order_service import PurchaseOrderService
from procurement.models import PurchaseOrder, PurchaseOrderItem
from partners.models import Partner
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestPurchaseOrderService:

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='svcuser', password='password')

    @pytest.fixture
    def partner(self, user):
        return Partner.objects.create(name="Service Supplier", code="SVC-SUPP", is_supplier=True, created_by=user)

    @pytest.fixture
    def item(self, user):
        cat = Category.objects.create(name="Test Cat", code="TC", created_by=user)
        return Item.objects.create(sku="SVC-ITEM", name="Service Item", unit="pcs", category=cat, created_by=user)

    def test_create_po_with_items(self, user, partner, item):
        items_data = [
            {'item': item, 'order_qty': 100, 'unit_cost': 10.5}
        ]
        po = PurchaseOrderService.create(
            document_no="PO-SVC-001",
            partner=partner,
            user=user,
            items=items_data
        )
        assert po.document_no == "PO-SVC-001"
        assert po.items.count() == 1
        assert po.items.first().order_qty == 100

    def test_soft_delete_restriction(self, user, partner):
        po = PurchaseOrderService.create(
            document_no="PO-DELETE",
            partner=partner,
            user=user
        )
        # Change status to Submitted
        po.status = PurchaseOrder.Status.SUBMITTED
        po.save()

        with pytest.raises(Exception) as excinfo:
            PurchaseOrderService.soft_delete(po, user=user)
        assert "Only Draft or Cancelled POs can be deleted" in str(excinfo.value)
