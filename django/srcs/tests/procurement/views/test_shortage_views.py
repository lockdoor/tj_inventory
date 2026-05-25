import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission, Group
from procurement.models import Shortage, PurchaseOrder
from catalog.models import Item, Category, ItemPackaging
from partners.models import Partner


@pytest.mark.django_db
class TestShortageListViews:
    """
    Test suite for ShortageListView permissions, filtering, search, and dashboard integration.
    """

    @pytest.fixture
    def test_user(self):
        user = User.objects.create_user(username="authorized_user", password="password")
        # Grant view_purchaseorder permission required by ShortageListView
        perm = Permission.objects.get(codename="view_purchaseorder")
        user.user_permissions.add(perm)
        return user

    @pytest.fixture
    def unauthorized_user(self):
        return User.objects.create_user(username="unauthorized_user", password="password")

    @pytest.fixture
    def category(self, test_user):
        return Category.objects.create(name="Spare Parts", code="SPARE", created_by=test_user)

    @pytest.fixture
    def item_a(self, test_user, category):
        return Item.objects.create(sku="SKU-A", name="Widget A", unit="pcs", category=category, created_by=test_user)

    @pytest.fixture
    def item_b(self, test_user, category):
        return Item.objects.create(sku="SKU-B", name="Gadget B", unit="pcs", category=category, created_by=test_user)

    @pytest.fixture
    def partner(self, test_user):
        return Partner.objects.create(name="Supplier A", code="SUPA", is_supplier=True, created_by=test_user)

    @pytest.fixture
    def purchase_order(self, test_user, partner):
        return PurchaseOrder.objects.create(document_no="PO-2026-001", partner=partner, created_by=test_user)

    @pytest.fixture
    def stock_controller_user(self):
        user = User.objects.create_user(username="stock_controller", password="password")
        group, _ = Group.objects.get_or_create(name='stock_controller')
        user.groups.add(group)
        # Grant required permission
        perm = Permission.objects.get(codename="view_purchaseorder")
        user.user_permissions.add(perm)
        return user

    def test_shortage_list_view_permissions(self, client, unauthorized_user, test_user):
        url = reverse('procurement:shortage-list')

        # 1. Unauthenticated -> 403 Forbidden due to raise_exception=True
        response = client.get(url)
        assert response.status_code == 403

        # 2. Authenticated but unauthorized (lacking view_purchaseorder permission) -> 403 Forbidden
        client.force_login(unauthorized_user)
        response = client.get(url)
        assert response.status_code == 403

        # 3. Authorized -> 200 OK
        client.force_login(test_user)
        response = client.get(url)
        assert response.status_code == 200

    def test_shortage_list_view_kpis(self, client, test_user, item_a, item_b, purchase_order):
        # Create active shortages with various statuses and quantities
        Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("15.50"),
            status=Shortage.Status.PENDING,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-101",
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("10.00"),
            status=Shortage.Status.PENDING,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-102",
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_b,
            request_qty=Decimal("30.00"),
            status=Shortage.Status.PO_CREATED,
            purchase_order=purchase_order,
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_b,
            request_qty=Decimal("5.00"),
            status=Shortage.Status.CANCELLED,
            created_by=test_user
        )
        
        # Soft-deleted shortage
        deleted_shortage = Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("100.00"),
            status=Shortage.Status.PENDING,
            created_by=test_user
        )
        deleted_shortage.delete(user=test_user)

        client.force_login(test_user)
        url = reverse('procurement:shortage-list')
        response = client.get(url)

        assert response.status_code == 200
        context = response.context
        
        # Verify active non-deleted count (4 active shortages)
        assert len(context['shortages']) == 4
        
        # Verify dynamic KPI context calculations
        assert context['pending_count'] == 2
        assert context['po_created_count'] == 1
        assert context['total_pending_qty'] == 25.50  # 15.50 + 10.00
        assert context['unique_short_items'] == 1     # Only item_a is pending

    def test_shortage_list_view_search(self, client, test_user, item_a, item_b):
        Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("15.50"),
            status=Shortage.Status.PENDING,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-ALPHA",
            note="Urgent customer demand",
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_b,
            request_qty=Decimal("30.00"),
            status=Shortage.Status.PENDING,
            reference_type=Shortage.ReferenceType.SELL_ORDER,
            reference_id="SO-BETA",
            note="Normal replenishment",
            created_by=test_user
        )

        client.force_login(test_user)
        url = reverse('procurement:shortage-list')

        # 1. Search by SKU
        response = client.get(url, {'q': 'SKU-A'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].item == item_a

        # 2. Search by Item Name
        response = client.get(url, {'q': 'Gadget'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].item == item_b

        # 3. Search by Reference ID
        response = client.get(url, {'q': 'ALPHA'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].reference_id == "SO-ALPHA"

        # 4. Search by Note
        response = client.get(url, {'q': 'replenishment'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].note == "Normal replenishment"

        # 5. Search non-matching
        response = client.get(url, {'q': 'NONEXISTENT'})
        assert len(response.context['shortages']) == 0

    def test_shortage_list_view_status_filtering(self, client, test_user, item_a, item_b):
        Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("10.00"),
            status=Shortage.Status.PENDING,
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("20.00"),
            status=Shortage.Status.PO_CREATED,
            created_by=test_user
        )
        Shortage.objects.create(
            item=item_b,
            request_qty=Decimal("30.00"),
            status=Shortage.Status.CANCELLED,
            created_by=test_user
        )

        client.force_login(test_user)
        url = reverse('procurement:shortage-list')

        # 1. Filter: Pending
        response = client.get(url, {'status': 'pending'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].status == Shortage.Status.PENDING

        # 2. Filter: PO Created
        response = client.get(url, {'status': 'po_created'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].status == Shortage.Status.PO_CREATED

        # 3. Filter: Cancelled
        response = client.get(url, {'status': 'cancelled'})
        assert len(response.context['shortages']) == 1
        assert response.context['shortages'][0].status == Shortage.Status.CANCELLED

        # 4. Filter: All
        response = client.get(url, {'status': 'all'})
        assert len(response.context['shortages']) == 3

    def test_stock_controller_dashboard_integration(self, client, stock_controller_user):
        """
        Ensures the 'Material Shortages' card resolves cleanly for a stock controller dashboard view.
        """
        client.force_login(stock_controller_user)
        dashboard_url = reverse('dashboard:home')
        response = client.get(dashboard_url)

        assert response.status_code == 200
        modules = response.context.get('modules', [])
        
        # Verify shortage card metadata inside context
        shortage_card = next((m for m in modules if m['title'] == 'Material Shortages'), None)
        assert shortage_card is not None
        assert shortage_card['url'] == 'procurement:shortage-list'
        assert shortage_card['badge'] == 'Shortages'
        assert shortage_card['icon_name'] == 'alert-triangle'

    def test_shortage_create_view_permissions(self, client, unauthorized_user, test_user):
        url = reverse('procurement:shortage-create')

        # 1. Unauthenticated -> 403 Forbidden
        response = client.get(url)
        assert response.status_code == 403

        # 2. Authenticated but unauthorized -> 403 Forbidden
        client.force_login(unauthorized_user)
        response = client.get(url)
        assert response.status_code == 403

        # 3. Authorized -> 200 OK
        client.force_login(test_user)
        response = client.get(url)
        assert response.status_code == 200

    def test_shortage_create_view_get(self, client, test_user, item_a, item_b):
        client.force_login(test_user)
        url = reverse('procurement:shortage-create')
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context['page_title'] == "Record Material Shortage"
        
        # Verify active items are preloaded in the choice field
        form = response.context['form']
        item_choices = [choice[0] for choice in form.fields['item'].choices if choice[0]]
        assert item_a.pk in item_choices
        assert item_b.pk in item_choices

    def test_shortage_create_view_post_success(self, client, test_user, item_a):
        client.force_login(test_user)
        url = reverse('procurement:shortage-create')
        data = {
            'item': item_a.pk,
            'input_qty': '10.50',
            'reference_type': Shortage.ReferenceType.SELL_ORDER,
            'reference_id': 'SO-999',
            'note': 'Urgent requirement'
        }

        response = client.post(url, data)
        assert response.status_code == 302

        # Verify shortage created correctly
        shortage = Shortage.objects.get(reference_id='SO-999')
        assert response.url == reverse('procurement:shortage-detail', kwargs={'pk': shortage.pk})
        assert shortage.item == item_a
        assert shortage.request_qty == Decimal('10.50')
        assert shortage.reference_type == Shortage.ReferenceType.SELL_ORDER
        assert shortage.note == 'Urgent requirement'
        assert shortage.created_by == test_user
        assert shortage.status == Shortage.Status.PENDING

    def test_shortage_create_view_post_with_packaging(self, client, test_user, item_a):
        client.force_login(test_user)
        url = reverse('procurement:shortage-create')
        
        # Create an alternative packaging
        pkg = ItemPackaging.objects.create(
            item=item_a,
            name="Box",
            quantity=12,
            created_by=test_user
        )

        data = {
            'item': item_a.pk,
            'packaging': pkg.pk,
            'input_qty': '3.50',
            'reference_type': Shortage.ReferenceType.SELL_ORDER,
            'reference_id': 'SO-PACKAGED',
            'note': 'Packaging conversion test'
        }

        response = client.post(url, data)
        assert response.status_code == 302
        
        # Verify shortage was calculated with packaging multiplier: 3.50 * 12 = 42.00
        shortage = Shortage.objects.get(reference_id='SO-PACKAGED')
        assert shortage.item == item_a
        assert shortage.request_qty == Decimal('42.00')
        assert shortage.reference_type == Shortage.ReferenceType.SELL_ORDER
        assert shortage.created_by == test_user
        assert shortage.status == Shortage.Status.PENDING

    def test_shortage_create_view_post_invalid(self, client, test_user, item_a):
        client.force_login(test_user)
        url = reverse('procurement:shortage-create')
        
        # Test negative quantity
        data = {
            'item': item_a.pk,
            'input_qty': '-5.00',
            'reference_type': Shortage.ReferenceType.OTHER,
            'reference_id': '',
            'note': ''
        }
        response = client.post(url, data)
        assert response.status_code == 200
        assert not Shortage.objects.filter(request_qty='-5.00').exists()
        assert 'input_qty' in response.context['form'].errors

    def test_shortage_update_view_permissions(self, client, unauthorized_user, test_user, item_a):
        shortage = Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("10.00"),
            status=Shortage.Status.PENDING,
            created_by=test_user
        )
        url = reverse('procurement:shortage-update', kwargs={'pk': shortage.pk})

        # 1. Unauthenticated -> 403 Forbidden
        response = client.get(url)
        assert response.status_code == 403

        # 2. Authenticated but unauthorized -> 403 Forbidden
        client.force_login(unauthorized_user)
        response = client.get(url)
        assert response.status_code == 403

        # 3. Authorized -> 200 OK
        client.force_login(test_user)
        response = client.get(url)
        assert response.status_code == 200

    def test_shortage_update_view_get(self, client, test_user, item_a):
        import datetime
        shortage = Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("15.50"),
            status=Shortage.Status.PENDING,
            expected_date=datetime.date(2026, 6, 1),
            note="Pre-edit note",
            created_by=test_user
        )
        client.force_login(test_user)
        url = reverse('procurement:shortage-update', kwargs={'pk': shortage.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert "form" in response.context
        assert response.context['page_title'] == f"Edit Material Shortage: {item_a.sku}"

        # Verify pre-populated values in form
        form = response.context['form']
        assert form.initial['input_qty'] == Decimal("15.50")
        assert form.initial['note'] == "Pre-edit note"
        assert form.initial['expected_date'] == shortage.expected_date

    def test_shortage_update_view_post_success(self, client, test_user, item_a, item_b):
        shortage = Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("15.50"),
            status=Shortage.Status.PENDING,
            created_by=test_user
        )
        client.force_login(test_user)
        url = reverse('procurement:shortage-update', kwargs={'pk': shortage.pk})
        data = {
            'item': item_b.pk,
            'input_qty': '25.00',
            'expected_date': '2026-07-15',
            'reference_type': Shortage.ReferenceType.PRODUCTION,
            'reference_id': 'PROD-777',
            'note': 'Updated notes here'
        }

        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse('procurement:shortage-detail', kwargs={'pk': shortage.pk})

        # Reload from DB and verify updates
        shortage.refresh_from_db()
        assert shortage.item == item_b
        assert shortage.request_qty == Decimal("25.00")
        assert shortage.expected_date.strftime("%Y-%m-%d") == "2026-07-15"
        assert shortage.reference_type == Shortage.ReferenceType.PRODUCTION
        assert shortage.reference_id == "PROD-777"
        assert shortage.note == "Updated notes here"
        assert shortage.updated_by == test_user

    def test_shortage_update_view_post_blocked_non_pending(self, client, test_user, item_a):
        # Create non-pending (PO_CREATED) shortage
        shortage = Shortage.objects.create(
            item=item_a,
            request_qty=Decimal("15.50"),
            status=Shortage.Status.PO_CREATED,
            created_by=test_user
        )
        client.force_login(test_user)
        url = reverse('procurement:shortage-update', kwargs={'pk': shortage.pk})
        data = {
            'item': item_a.pk,
            'input_qty': '30.00',
            'note': 'Hacked edit'
        }

        response = client.post(url, data)
        # Should redirect to detail view
        assert response.status_code == 302
        assert response.url == reverse('procurement:shortage-detail', kwargs={'pk': shortage.pk})

        # Verify DB is unchanged
        shortage.refresh_from_db()
        assert shortage.request_qty == Decimal("15.50")
        assert shortage.note != "Hacked edit"

        # Direct test on service layer to check custom ValidationError
        from procurement.services.shortage_service import ShortageService
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Only pending shortages can be updated."):
            ShortageService.update(shortage, user=test_user, request_qty=Decimal("30.00"))



