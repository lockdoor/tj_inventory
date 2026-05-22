import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from partners.models import Partner
from sales.models import SalesOrder, SalesOrderItem
from sales.services.sales_service import SalesService
from datetime import date

@pytest.fixture
def user(db):
    user = User.objects.create_user(username='staff', password='password123')
    # Grant view_salesorder permission
    perm = Permission.objects.get(codename='view_salesorder')
    user.user_permissions.add(perm)
    return user

@pytest.fixture
def partner(db, user):
    return Partner.objects.create(name="Customer 1", code="CUST001", is_customer=True, created_by=user)

@pytest.mark.django_db
class TestSalesOverviewView:
    def test_unauthenticated_denied(self, client):
        url = reverse('sales:overview')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden due to raise_exception = True

    def test_missing_permission_denied(self, client):
        # Create user without view_salesorder permission
        u = User.objects.create_user(username='no-perm', password='password123')
        client.login(username='no-perm', password='password123')
        url = reverse('sales:overview')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_authorized_access_and_metrics(self, client, user, partner):
        client.login(username='staff', password='password123')
        url = reverse('sales:overview')

        # Create active sales orders of different statuses
        # Confirmed
        order_confirmed = SalesService.create_order(
            document_no="SO-CONF",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        order_confirmed.status = SalesOrder.Status.CONFIRMED
        order_confirmed.save()

        # Preorder
        order_preorder = SalesService.create_order(
            document_no="SO-PRE",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.PREORDER
        )
        order_preorder.status = SalesOrder.Status.PREORDER
        order_preorder.save()

        # Draft
        order_draft = SalesService.create_order(
            document_no="SO-DRAFT",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        order_draft.status = SalesOrder.Status.DRAFT
        order_draft.save()

        # Cancelled
        order_cancelled = SalesService.create_order(
            document_no="SO-CANCEL",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        order_cancelled.status = SalesOrder.Status.CANCELLED
        order_cancelled.save()

        # Soft-deleted order (should NOT count anywhere)
        order_deleted = SalesService.create_order(
            document_no="SO-DELETED",
            partner=partner,
            user=user,
            order_date=date.today(),
            order_type=SalesOrder.OrderType.NORMAL
        )
        order_deleted.status = SalesOrder.Status.CONFIRMED
        order_deleted.is_deleted = True
        order_deleted.save()

        # Add items to calculate revenue
        from catalog.models import Item
        catalog_item = Item.objects.create(sku="SKU1", name="Item 1", created_by=user)
        SalesService.add_item(order_confirmed, item=catalog_item, requested_qty=10, unit_price=10.00)
        SalesService.add_item(order_preorder, item=catalog_item, requested_qty=5, unit_price=20.00) # 100.00
        SalesService.add_item(order_draft, item=catalog_item, requested_qty=2, unit_price=15.00) # 30.00
        
        # Add manually to cancelled order
        SalesOrderItem.objects.create(order=order_cancelled, item=catalog_item, requested_qty=1, unit_price=50.00)
        # Add manually to deleted order
        SalesOrderItem.objects.create(order=order_deleted, item=catalog_item, requested_qty=10, unit_price=100.00)

        response = client.get(url)
        assert response.status_code == 200
        assert response.context['page_title'] == "Sales Overview"
        assert response.context['confirmed_count'] == 1
        assert response.context['preorder_count'] == 1
        assert response.context['draft_count'] == 1
        
        # total active revenue = 100 (confirmed) + 100 (preorder) + 30 (draft) + 50 (cancelled) = 280
        assert float(response.context['total_revenue']) == 280.0
        assert b"Sales Overview" in response.content


@pytest.mark.django_db
class TestSalesOrderListView:
    def test_unauthenticated_denied(self, client):
        url = reverse('sales:sales-order-list')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden due to raise_exception = True

    def test_missing_permission_denied(self, client):
        u = User.objects.create_user(username='no-perm', password='password123')
        client.login(username='no-perm', password='password123')
        url = reverse('sales:sales-order-list')
        response = client.get(url)
        assert response.status_code == 403  # Forbidden

    def test_authorized_list_and_search(self, client, user, partner):
        client.login(username='staff', password='password123')
        url = reverse('sales:sales-order-list')

        # Create partner 2 for specific search
        partner2 = Partner.objects.create(name="Acme Corp", code="CUST002", is_customer=True, created_by=user)

        # Create sales orders
        order1 = SalesService.create_order(document_no="SO-9001", partner=partner, user=user)
        order2 = SalesService.create_order(document_no="SO-9002", partner=partner2, user=user)
        
        # Soft-deleted order (should NOT appear)
        order_del = SalesService.create_order(document_no="SO-DEL", partner=partner, user=user)
        order_del.is_deleted = True
        order_del.save()

        # Verify default list
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['sales_orders']) == 2
        
        # Search by Document No
        response_search_doc = client.get(url, {'q': '9001'})
        assert len(response_search_doc.context['sales_orders']) == 1
        assert response_search_doc.context['sales_orders'][0].document_no == "SO-9001"

        # Search by Customer Name
        response_search_cust = client.get(url, {'q': 'Acme'})
        assert len(response_search_cust.context['sales_orders']) == 1
        assert response_search_cust.context['sales_orders'][0].document_no == "SO-9002"

        # Search with no matches
        response_no_match = client.get(url, {'q': 'NonExistent'})
        assert len(response_no_match.context['sales_orders']) == 0
