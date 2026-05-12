import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from procurement.models import PurchaseOrder
from partners.models import Partner
from catalog.models import Item

@pytest.mark.django_db
class TestPurchaseOrderPermissions:
    
    @pytest.fixture
    def supplier(self, authorized_user):
        return Partner.objects.create(
            name="Supplier A", 
            code="SUPA", 
            is_supplier=True, 
            status='active',
            created_by=authorized_user
        )

    @pytest.fixture
    def item(self):
        return Item.objects.create(name="Widget", sku="WID-001")

    @pytest.fixture
    def unauthorized_user(self):
        return User.objects.create_user(username="unauthorized", password="password")

    @pytest.fixture
    def authorized_user(self):
        user = User.objects.create_user(username="authorized", password="password")
        # Add necessary permissions
        perms = Permission.objects.filter(codename__in=[
            'view_purchaseorder', 'add_purchaseorder', 'change_purchaseorder'
        ])
        user.user_permissions.add(*perms)
        return user

    def test_list_view_permission(self, client, unauthorized_user, authorized_user):
        url = reverse('procurement:purchase-order-list')
        
        # Unauthenticated
        response = client.get(url)
        assert response.status_code == 302 # Redirect to login

        # Unauthorized
        client.login(username="unauthorized", password="password")
        response = client.get(url)
        assert response.status_code == 403

        # Authorized
        client.login(username="authorized", password="password")
        response = client.get(url)
        assert response.status_code == 200

    def test_create_view_permission(self, client, unauthorized_user, authorized_user):
        url = reverse('procurement:purchase-order-create')
        
        # Unauthorized
        client.login(username="unauthorized", password="password")
        response = client.get(url)
        assert response.status_code == 403

        # Authorized
        client.login(username="authorized", password="password")
        response = client.get(url)
        assert response.status_code == 200

    def test_update_view_permission(self, client, authorized_user, unauthorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-TEST-001",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=authorized_user
        )
        url = reverse('procurement:purchase-order-update', kwargs={'pk': po.pk})
        
        # Unauthorized
        client.login(username="unauthorized", password="password")
        response = client.get(url)
        assert response.status_code == 403

        # Authorized
        client.login(username="authorized", password="password")
        response = client.get(url)
        assert response.status_code == 200

    def test_update_non_draft_po_denied(self, client, authorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-TEST-002",
            partner=supplier,
            status=PurchaseOrder.Status.SUBMITTED,
            created_by=authorized_user
        )
        url = reverse('procurement:purchase-order-update', kwargs={'pk': po.pk})
        
        client.login(username="authorized", password="password")
        response = client.get(url)
        assert response.status_code == 403 # PermissionDenied raises 403
