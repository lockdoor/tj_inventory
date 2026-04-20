import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from inventory.models import StockCard, Warehouse, Stock
from catalog.models import Item

@pytest.fixture
def user(db):
    user = User.objects.create_user(username='tester')
    # Grant necessary permissions
    perms = Permission.objects.filter(codename__in=['view_stockcard', 'view_inventorymovement'])
    user.user_permissions.add(*perms)
    return user

@pytest.fixture
def stock_card(db, user):
    warehouse = Warehouse.objects.create(name='W1', code='W1', created_by=user)
    item = Item.objects.create(name='Item A', sku='SKUA', created_by=user)
    stock = Stock.objects.create(warehouse=warehouse, item=item, lot_number='LOT1', balance=100, created_by=user)
    
    return StockCard.objects.create(
        stock=stock,
        warehouse=warehouse,
        item=item,
        lot_number='LOT1',
        quantity=10,
        type=StockCard.StockCardType.IN,
        created_by=user
    )

@pytest.mark.django_db
class TestStockCardViews:
    def test_stockcard_list_view_accessible(self, client, user, stock_card):
        client.force_login(user)
        url = reverse('inventory:stockcard-list')
        response = client.get(url)
        assert response.status_code == 200
        assert 'stockcards' in response.context
        assert stock_card in response.context['stockcards']

    def test_stockcard_list_view_pagination(self, client, user, stock_card):
        # Create 20 more stock cards
        total = 21
        for i in range(20):
             StockCard.objects.create(
                stock=stock_card.stock,
                warehouse=stock_card.warehouse,
                item=stock_card.item,
                lot_number=f'LOT{i}',
                quantity=1,
                type=StockCard.StockCardType.IN,
                created_by=user
            )
        
        client.force_login(user)
        url = reverse('inventory:stockcard-list')
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['stockcards']) == 15  # Default paginate_by
        assert response.context['is_paginated'] is True

    def test_stockcard_detail_view_accessible(self, client, user, stock_card):
        client.force_login(user)
        url = reverse('inventory:stockcard-detail', kwargs={'pk': stock_card.pk})
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['stockcard'] == stock_card
        assert stock_card.item.name.encode() in response.content
