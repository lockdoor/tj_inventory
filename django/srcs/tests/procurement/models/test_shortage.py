import pytest
from django.contrib.auth import get_user_model
from procurement.models.shortage import Shortage
from procurement.models.purchase_order import PurchaseOrder
from partners.models.partner import Partner
from catalog.models import Item, Category

User = get_user_model()

@pytest.mark.django_db
class TestShortageModel:
    """
    Unit tests for the Shortage model.
    """

    @pytest.fixture
    def user(self):
        return User.objects.create_user(username='shortageuser', password='password')

    @pytest.fixture
    def category(self, user):
        return Category.objects.create(name="Spare Parts", code="SPARE", created_by=user)

    @pytest.fixture
    def item(self, user, category):
        return Item.objects.create(sku="SP-001", name="Gasket", unit="pcs", category=category, created_by=user)

    @pytest.fixture
    def partner(self, user):
        return Partner.objects.create(name="Supplier C", code="SUPP-C", is_supplier=True, created_by=user)

    @pytest.fixture
    def po(self, user, partner):
        return PurchaseOrder.objects.create(document_no="PO-SHORTAGE-RESOLVE", partner=partner, created_by=user)

    def test_shortage_creation(self, user, item):
        """Verify that a shortage can be created with required fields."""
        shortage = Shortage.objects.create(
            item=item,
            request_qty=50.50,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-123",
            created_by=user
        )
        assert shortage.item == item
        assert shortage.request_qty == 50.50
        assert shortage.reference_type == Shortage.ReferenceType.SELL_ORDER
        assert shortage.status == Shortage.Status.PENDING
        assert str(shortage) == "Shortage: SP-001 (50.5) - pending"

    def test_shortage_po_linking(self, user, item, po):
        """Verify that a shortage can be linked to a Purchase Order."""
        shortage = Shortage.objects.create(
            item=item,
            request_qty=100,
            status=Shortage.Status.PO_CREATED,
            purchase_order=po,
            created_by=user
        )
        assert shortage.purchase_order == po
        assert shortage.status == Shortage.Status.PO_CREATED

    def test_audit_fields(self, user, item):
        """Verify that AuditableMixin tracks metadata for Shortage."""
        shortage = Shortage.objects.create(
            item=item,
            request_qty=10,
            created_by=user
        )
        assert shortage.created_by == user
        assert shortage.created_at is not None
        assert shortage.version == 1
