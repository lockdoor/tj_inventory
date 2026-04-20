import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from inventory.models import Stock, Warehouse
from catalog.models import Item
from inventory.services.stock_service import StockService

@pytest.fixture
def user(db):
    user = User.objects.create_user(username='tester')
    perms = Permission.objects.filter(codename__in=['view_stock'])
    user.user_permissions.add(*perms)
    return user

@pytest.fixture
def stock_setup(db, user):
    w1 = Warehouse.objects.create(name='WH1', code='WH1', created_by=user)
    w2 = Warehouse.objects.create(name='WH2', code='WH2', created_by=user)
    
    i1 = Item.objects.create(name='Item1', sku='SKU1', created_by=user)
    i2 = Item.objects.create(name='Item2', sku='SKU2', created_by=user)
    
    # WH1 - Item1: 10 + 20 = 30
    Stock.objects.create(warehouse=w1, item=i1, lot_number='L1', balance=10, created_by=user)
    Stock.objects.create(warehouse=w1, item=i1, lot_number='L2', balance=20, created_by=user)
    
    # WH1 - Item2: 50
    Stock.objects.create(warehouse=w1, item=i2, lot_number='L3', balance=50, created_by=user)
    
    # WH2 - Item1: 100
    Stock.objects.create(warehouse=w2, item=i1, lot_number='L4', balance=100, created_by=user)
    
    return {'wh1': w1, 'wh2': w2, 'item1': i1, 'item2': i2}

@pytest.mark.django_db
class TestStockBalanceModule:
    def test_stock_service_grouping(self, stock_setup):
        hierarchy = StockService.get_hierarchical_stock_balances()
        
        assert len(hierarchy) == 2  # 2 Warehouses
        
        # Check WH1
        wh1_data = next(h for h in hierarchy if h['warehouse'].name == 'WH1')
        assert wh1_data['total_balance'] == 80  # 10 + 20 + 50
        assert len(wh1_data['items']) == 2
        
        # Check Item1 in WH1
        i1_data = next(i for i in wh1_data['items'] if i['item'].sku == 'SKU1')
        assert i1_data['total_balance'] == 30
        assert len(i1_data['lots']) == 2

    def test_stock_balance_view_accessible(self, client, user, stock_setup):
        client.force_login(user)
        url = reverse('inventory:stock-balance-list')
        response = client.get(url)
        assert response.status_code == 200
        assert 'hierarchy' in response.context
        assert b'WH1' in response.content
        assert b'SKU1' in response.content
