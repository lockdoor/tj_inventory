from django.db.models import Sum
from inventory.models import Stock, Warehouse
from catalog.models import Item
from collections import defaultdict

class StockService:
    """
    Service layer for complex stock queries and balance reporting.
    """

    @staticmethod
    def get_hierarchical_stock_balances():
        """
        Retrieves all stock records and groups them into a hierarchical structure:
        Warehouse -> Item -> Lots
        
        Returns a structured list for template rendering.
        """
        # Fetch all stock with balances, optimized
        stocks = Stock.objects.select_related('warehouse', 'item').all().order_by(
            'warehouse__name', 'item__name', 'lot_number'
        )
        
        # Build hierarchy
        hierarchy = defaultdict(lambda: {
            'warehouse': None,
            'total_balance': 0,
            'items': defaultdict(lambda: {
                'item': None,
                'total_balance': 0,
                'lots': []
            })
        })
        
        for s in stocks:
            wh_id = s.warehouse.id
            item_id = s.item.id
            
            # Initialize Warehouse
            if hierarchy[wh_id]['warehouse'] is None:
                hierarchy[wh_id]['warehouse'] = s.warehouse
            
            # Initialize Item
            if hierarchy[wh_id]['items'][item_id]['item'] is None:
                hierarchy[wh_id]['items'][item_id]['item'] = s.item
            
            # Add Lot
            hierarchy[wh_id]['items'][item_id]['lots'].append(s)
            
            # Update Totals
            hierarchy[wh_id]['items'][item_id]['total_balance'] += s.balance
            hierarchy[wh_id]['total_balance'] += s.balance

        # Convert to list for easier template iteration
        result = []
        for wh_data in sorted(hierarchy.values(), key=lambda x: x['warehouse'].name):
            # Sort items within warehouse
            items_list = sorted(wh_data['items'].values(), key=lambda x: x['item'].name)
            wh_data['items'] = items_list
            result.append(wh_data)
            
        return result
