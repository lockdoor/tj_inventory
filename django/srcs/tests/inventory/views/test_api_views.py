import pytest
from django.urls import reverse
from inventory.models import Stock

@pytest.mark.django_db
class TestAvailableLotsAPIView:
    def test_get_available_lots(self, client, admin_user):
        client.force_login(admin_user)
        
        from inventory.models import Warehouse
        from catalog.models import Item, Category
        
        warehouse = Warehouse.objects.create(name="Test WH", code="WH01", created_by=admin_user)
        category = Category.objects.create(name="Test Cat", code="CAT01", created_by=admin_user)
        item = Item.objects.create(name="Test Item", sku="ITEM01", unit="pcs", category=category, created_by=admin_user)
        
        # Create some stock
        Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="LOT-123",
            balance=100,
            created_by=admin_user
        )
        Stock.objects.create(
            warehouse=warehouse,
            item=item,
            lot_number="LOT-456",
            balance=50,
            created_by=admin_user
        )
        
        url = reverse('inventory:api-lots')
        response = client.get(url, {'warehouse_id': warehouse.id, 'item_id': item.id})
        
        assert response.status_code == 200
        data = response.json()
        assert 'lots' in data
        assert len(data['lots']) == 2
        
        lots = {lot['lot_number']: lot['balance'] for lot in data['lots']}
        assert lots['LOT-123'] == 100
        assert lots['LOT-456'] == 50

    def test_missing_params(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('inventory:api-lots')
        response = client.get(url)
        assert response.status_code == 400
