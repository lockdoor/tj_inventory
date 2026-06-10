import pytest
from django.urls import reverse
from decimal import Decimal
from django.contrib.auth.models import User, Permission
from procurement.models import PurchaseOrder, Shortage
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
    def item(self, authorized_user):
        return Item.objects.create(name="Widget", sku="WID-001", created_by=authorized_user)

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

    def test_create_view_prefills_suggested_document_no(self, client, authorized_user):
        client.login(username="authorized", password="password")
        url = reverse('procurement:purchase-order-create')
        response = client.get(url)
        assert response.status_code == 200
        form = response.context['form']
        assert form.initial.get('document_no') is not None
        assert form.initial.get('document_no').startswith("PO-")

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

    def test_create_from_shortage_view_get_and_post(self, client, authorized_user, unauthorized_user, supplier, item):
        # Create a pending shortage
        shortage = Shortage.objects.create(
            item=item,
            request_qty=10.0,
            status='pending',
            reference_type='other',
            reference_id='REQ-001',
            created_by=authorized_user
        )
        
        url = reverse('procurement:purchase-order-create-from-shortage')
        
        # Test unauthorized GET
        client.login(username="unauthorized", password="password")
        response = client.get(f"{url}?shortage_ids={shortage.pk}")
        assert response.status_code == 403
        
        # Test authorized GET
        client.login(username="authorized", password="password")
        response = client.get(f"{url}?shortage_ids={shortage.pk}")
        assert response.status_code == 200
        assert b"Create Purchase Order from Shortages" in response.content
        assert b"WID-001" in response.content

        # Test POST creation
        import json
        payload = {
            'partner': supplier.pk,
            'document_no': 'PO-FROM-SHORT-001',
            'expected_date': '2026-06-15',
            'note': 'Test PO note',
            'shortage_ids': str(shortage.pk),
            'items_json': json.dumps([{
                'item_id': item.pk,
                'order_qty': 10.0,
                'unit_cost': None,
                'packaging_id': None
            }])
        }
        response = client.post(url, data=payload)
        assert response.status_code == 302 # Redirect on success
        
        # Verify PO was created and shortage linked
        po = PurchaseOrder.objects.get(document_no='PO-FROM-SHORT-001')
        assert po.partner == supplier
        assert po.items.count() == 1
        po_item = po.items.first()
        assert po_item.order_qty == 10.0
        assert po_item.unit_cost == Decimal('0.00')
        
        shortage.refresh_from_db()
        assert shortage.status == 'po_created'
        assert shortage.purchase_order == po

        # Test POST creation with unit_cost specified
        # Create another pending shortage
        shortage2 = Shortage.objects.create(
            item=item,
            request_qty=5.0,
            status='pending',
            reference_type='other',
            reference_id='REQ-002',
            created_by=authorized_user
        )
        payload2 = {
            'partner': supplier.pk,
            'document_no': 'PO-FROM-SHORT-002',
            'expected_date': '2026-06-15',
            'note': 'Test PO note 2',
            'shortage_ids': str(shortage2.pk),
            'items_json': json.dumps([{
                'item_id': item.pk,
                'order_qty': 5.0,
                'unit_cost': 12.50,
                'packaging_id': None
            }])
        }
        response = client.post(url, data=payload2)
        assert response.status_code == 302 # Redirect on success

        # Verify PO was created with unit_cost = 12.50
        po2 = PurchaseOrder.objects.get(document_no='PO-FROM-SHORT-002')
        po_item2 = po2.items.first()
        assert po_item2.order_qty == 5.0
        assert po_item2.unit_cost == Decimal('12.50')
