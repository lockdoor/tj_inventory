import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from procurement.models import PurchaseOrder, Arrival
from partners.models import Partner
from inventory.models import Warehouse

@pytest.mark.django_db
class TestPurchaseOrderDeleteView:
    
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
    def unauthorized_user(self):
        return User.objects.create_user(username="unauthorized", password="password")

    @pytest.fixture
    def authorized_user(self):
        user = User.objects.create_user(username="authorized", password="password")
        perms = Permission.objects.filter(codename__in=[
            'view_purchaseorder', 'delete_purchaseorder'
        ])
        user.user_permissions.add(*perms)
        return user

    def test_delete_unauthenticated_redirects(self, client, unauthorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-UNAUTH-DEL",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=unauthorized_user
        )
        url = reverse('procurement:purchase-order-delete', kwargs={'pk': po.pk})
        
        response = client.post(url)
        assert response.status_code == 302
        assert 'login' in response.url

    def test_delete_unauthorized_denied(self, client, unauthorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-DENY-DEL",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=unauthorized_user
        )
        url = reverse('procurement:purchase-order-delete', kwargs={'pk': po.pk})
        
        client.login(username="unauthorized", password="password")
        response = client.post(url)
        assert response.status_code == 403

    def test_delete_success(self, client, authorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-OK-DEL",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=authorized_user
        )
        url = reverse('procurement:purchase-order-delete', kwargs={'pk': po.pk})
        
        client.login(username="authorized", password="password")
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('procurement:purchase-order-list')
        
        po.refresh_from_db()
        assert po.is_deleted

    def test_delete_failure_with_arrivals(self, client, authorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-ERR-DEL",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=authorized_user
        )
        
        warehouse = Warehouse.objects.create(name="WH A", code="WHA", created_by=authorized_user)
        Arrival.objects.create(
            document_no="ARR-ERR-DEL",
            partner=supplier,
            warehouse=warehouse,
            expected_date="2026-05-20",
            purchase_order=po,
            created_by=authorized_user
        )
        
        url = reverse('procurement:purchase-order-delete', kwargs={'pk': po.pk})
        
        client.login(username="authorized", password="password")
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('procurement:purchase-order-detail', kwargs={'pk': po.pk})
        
        po.refresh_from_db()
        assert not po.is_deleted
