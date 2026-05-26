import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from sales.models import SalesOrder, SalesOrderItem, SalesAllocation
from catalog.models import Item, Category
from partners.models import Partner
from inventory.models import Warehouse, Stock
from procurement.models import Arrival, ArrivalItem, Shortage


@pytest.mark.django_db
class TestSalesOrderDetailAndRefreshViews:
    """
    Test suite for SalesOrderDetailView and SalesOrderRefreshAllocationView.
    """

    @pytest.fixture
    def test_user(self):
        user = User.objects.create_user(username="authorized_user", password="password")
        # Grant view_salesorder and change_salesorder permissions
        perm_view = Permission.objects.get(codename="view_salesorder")
        perm_change = Permission.objects.get(codename="change_salesorder")
        user.user_permissions.add(perm_view, perm_change)
        return user

    @pytest.fixture
    def unauthorized_user(self):
        return User.objects.create_user(username="unauthorized_user", password="password")

    @pytest.fixture
    def category(self, test_user):
        return Category.objects.create(name="Spare Parts", code="SPARE", created_by=test_user)

    @pytest.fixture
    def item(self, test_user, category):
        return Item.objects.create(sku="SKU-TEST", name="Test Item", unit="pcs", category=category, created_by=test_user)

    @pytest.fixture
    def customer(self, test_user):
        return Partner.objects.create(name="Customer Corp", code="CUST01", is_customer=True, created_by=test_user)

    @pytest.fixture
    def warehouse(self, test_user):
        return Warehouse.objects.create(name="Main WH", code="WH-01", created_by=test_user)

    @pytest.fixture
    def sales_order(self, test_user, customer, item):
        from sales.services.sales_service import SalesService
        order = SalesService.create_order(
            document_no="SO-2026-999",
            partner=customer,
            user=test_user,
            order_type=SalesOrder.OrderType.NORMAL,
            items=[{
                'item': item,
                'requested_qty': Decimal("10.00"),
                'unit_price': Decimal("100.00")
            }]
        )
        return order

    def test_sales_order_detail_view_permissions(self, client, unauthorized_user, test_user, sales_order):
        url = reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

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

    def test_sales_order_detail_view_content(self, client, test_user, sales_order, item):
        client.force_login(test_user)
        url = reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        response = client.get(url)

        assert response.status_code == 200
        assert response.context['sales_order'] == sales_order
        assert response.context['total_amount'] == 1000.00  # 10.00 * 100.00
        assert response.context['total_items'] == 1

        # Initially, there is no stock so the smart allocator creates a shortage allocation
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.PENDING
        assert item_line.allocations.count() == 1
        alloc = item_line.allocations.first()
        assert alloc.source_type == SalesAllocation.SourceType.SHORTAGE
        assert alloc.quantity == Decimal("10.00")
        assert alloc.shortage is not None

    def test_refresh_allocations_view_post_success(self, client, test_user, sales_order, item, warehouse):
        # Create physical stock so we can fulfill the shortage gap upon refresh
        Stock.objects.create(
            item=item,
            warehouse=warehouse,
            lot_number="LOT-AAA",
            balance=Decimal("20.00"),
            reserved_qty=Decimal("0.00"),
            created_by=test_user
        )

        client.force_login(test_user)
        
        # Verify there is a shortage allocation before refresh
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.PENDING
        assert item_line.allocations.filter(source_type=SalesAllocation.SourceType.SHORTAGE).exists()

        # Trigger POST refresh allocations
        url = reverse('sales:sales-order-refresh-allocations', kwargs={'pk': sales_order.pk})
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})

        # Reload item line and verify allocations are refreshed to stock reservation
        item_line.refresh_from_db()
        assert item_line.status == SalesOrderItem.Status.ALLOCATED
        assert item_line.allocated_qty == Decimal("10.00")
        assert item_line.allocations.count() == 1
        
        alloc = item_line.allocations.first()
        assert alloc.source_type == SalesAllocation.SourceType.STOCK
        assert alloc.quantity == Decimal("10.00")
        assert alloc.physical_reservation is not None
        assert alloc.physical_reservation.stock.lot_number == "LOT-AAA"

    def test_refresh_allocations_view_post_blocked_cancelled(self, client, test_user, sales_order):
        # Cancel the sales order
        from sales.services.sales_service import SalesService
        SalesService.cancel_order(sales_order, user=test_user)
        assert sales_order.status == SalesOrder.Status.CANCELLED

        client.force_login(test_user)
        url = reverse('sales:sales-order-refresh-allocations', kwargs={'pk': sales_order.pk})
        response = client.post(url)

        assert response.status_code == 302
        assert response.url == reverse('sales:sales-order-detail', kwargs={'pk': sales_order.pk})
        
        # Verify no items were allocated
        item_line = sales_order.items.first()
        assert item_line.status == SalesOrderItem.Status.CANCELLED
