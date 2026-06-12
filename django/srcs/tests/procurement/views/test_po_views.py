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

    def test_create_po_from_shortage_expected_date_validation(self, client, authorized_user, supplier, item):
        from datetime import date
        # Create shortages with different expected dates
        shortage1 = Shortage.objects.create(
            item=item,
            request_qty=5.0,
            status='pending',
            reference_type='other',
            reference_id='REQ-003',
            expected_date=date(2026, 6, 12),
            created_by=authorized_user
        )
        shortage2 = Shortage.objects.create(
            item=item,
            request_qty=5.0,
            status='pending',
            reference_type='other',
            reference_id='REQ-004',
            expected_date=date(2026, 6, 18),
            created_by=authorized_user
        )

        url = reverse('procurement:purchase-order-create-from-shortage')
        client.login(username="authorized", password="password")

        # 1. GET request: check prefilled expected date is the latest date (2026-06-18)
        response = client.get(f"{url}?shortage_ids={shortage1.pk},{shortage2.pk}")
        assert response.status_code == 200
        assert response.context['selected_expected_date'] == '2026-06-18'
        # Verify that the expected date display is present in the rendered content
        assert b"Expected Date: 12 Jun 2026 to 18 Jun 2026" in response.content

        # 2. POST request: try to create a PO with expected_date = 2026-06-15 (less than shortage2's expected_date of 2026-06-18)
        import json
        payload_fail = {
            'partner': supplier.pk,
            'document_no': 'PO-EXPECTED-FAIL',
            'expected_date': '2026-06-15',
            'note': 'Should fail',
            'shortage_ids': f"{shortage1.pk},{shortage2.pk}",
            'items_json': json.dumps([{
                'item_id': item.pk,
                'order_qty': 10.0,
                'unit_cost': None,
                'packaging_id': None
            }])
        }
        response = client.post(url, data=payload_fail)
        # Should not redirect (stay on form page due to validation error)
        assert response.status_code == 200
        # Check that error is in messages
        messages_list = list(response.context['messages'])
        assert any("cannot be earlier than shortage expected date of 2026-06-18" in str(m) for m in messages_list)
        # Verify PO was not created
        assert not PurchaseOrder.objects.filter(document_no='PO-EXPECTED-FAIL').exists()

        # 3. POST request: create a PO with expected_date = 2026-06-20 (greater than both shortage expected dates)
        payload_success = {
            'partner': supplier.pk,
            'document_no': 'PO-EXPECTED-SUCCESS',
            'expected_date': '2026-06-20',
            'note': 'Should succeed',
            'shortage_ids': f"{shortage1.pk},{shortage2.pk}",
            'items_json': json.dumps([{
                'item_id': item.pk,
                'order_qty': 10.0,
                'unit_cost': None,
                'packaging_id': None
            }])
        }
        response = client.post(url, data=payload_success)
        assert response.status_code == 302 # Success redirect
        
        # Verify PO was successfully created
        po = PurchaseOrder.objects.get(document_no='PO-EXPECTED-SUCCESS')
        assert po.expected_date == date(2026, 6, 20)

    def test_close_view_success(self, client, authorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-CLOSE-001",
            partner=supplier,
            status=PurchaseOrder.Status.SUBMITTED,
            created_by=authorized_user
        )
        url = reverse('procurement:purchase-order-close', kwargs={'pk': po.pk})
        client.login(username="authorized", password="password")
        
        response = client.post(url)
        assert response.status_code == 302 # Redirect on success
        
        po.refresh_from_db()
        assert po.status == PurchaseOrder.Status.CLOSED

    def test_close_view_blocked_for_draft(self, client, authorized_user, supplier):
        po = PurchaseOrder.objects.create(
            document_no="PO-CLOSE-002",
            partner=supplier,
            status=PurchaseOrder.Status.DRAFT,
            created_by=authorized_user
        )
        url = reverse('procurement:purchase-order-close', kwargs={'pk': po.pk})
        client.login(username="authorized", password="password")
        
        response = client.post(url)
        assert response.status_code == 302 # Redirect back to detail with error message
        
        po.refresh_from_db()
        assert po.status == PurchaseOrder.Status.DRAFT

