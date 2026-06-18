import requests
import json
from django.conf import settings
from inventory.services.stock_service import StockService
from inventory.models import Stock, Warehouse

class ExpressService:
    """
    Service for integrating with Express ERP via a FastAPI Bridge.
    """

    @staticmethod
    def get_express_location():
        """Get Express ERP location."""
        return getattr(settings, 'EXPRESS_LOCATION', None)
    
    @staticmethod
    def is_configured():
        """Check if any Express bridge endpoints are configured."""
        return bool(getattr(settings, 'EXPRESS_LOCATION', None))

    @staticmethod
    def is_alive():
        """Check if Express bridge is alive."""
        try:
            response = requests.get(ExpressService.get_express_location(), timeout=5)
            if (response.status_code != 200):
                raise Exception(f"Express Bridge returned error {response.status_code}: {response.text}")
            return True
        except Exception as e:
            return False

    @staticmethod
    def get_companies():
        """Get companies form setting.COMPANY_WAREHOUSE_CODES.keys()"""
        return getattr(settings, 'COMPANY_WAREHOUSE_CODES', {}).keys()

    @staticmethod
    def get_express_balances(company_id):
        """
        Fetches balances from the Express Bridge API.
        Returns a list of dictionaries of [{'sku': '00-1111-11', 'balance': 3132.0}]
        """
        if company_id not in ExpressService.get_companies():
            raise Exception(f"Company '{company_id}' not found")

        url = ExpressService.get_express_location() + '/stock/' + company_id
            
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {}
        except Exception as e:
            return {}

    @staticmethod
    def get_comparison_data(company_id):
        """
        Combines Django balances and Express balances (from Bridge).
        """
        company_warehouse_codes = getattr(settings, 'COMPANY_WAREHOUSE_CODES', {})
        if company_id not in company_warehouse_codes:
            raise Exception(f"Company '{company_id}' not found")

        target_wh_code = company_warehouse_codes.get(company_id)

        # 1. Fetch Internal Balances (aggregated by SKU)
        internal_data = Stock.objects.select_related('warehouse', 'item')
        if target_wh_code:
            internal_data = internal_data.filter(warehouse__code=target_wh_code)
        
        internal_data = internal_data.exclude(balance=0).order_by('item__name', 'lot_number')

        django_balances = {}
        for node in internal_data:
            item_obj = node.item
            sku = item_obj.sku
            django_balances[sku] = django_balances.get(sku, 0) + float(node.balance)

        # 2. Fetch Express Balances for this specific bridge URL
        express_data_list = ExpressService.get_express_balances(company_id)
        express_balances = {}
        if isinstance(express_data_list, list):
            for entry in express_data_list:
                sku = entry.get('sku')
                balance = entry.get('balance', 0)
                if sku:
                    express_balances[sku] = float(balance)

        # 3. Join and Compare
        results = []
        # Base results on items in Django (since it's the master)
        from catalog.models import Item
        all_items = Item.objects.filter(is_deleted=False)
        if target_wh_code:
            all_items = all_items.filter(stocks__warehouse__code=target_wh_code).distinct()
        all_items = all_items.order_by('sku')
        
        for item in all_items:
            django_qty = django_balances.get(item.sku, 0)
            express_qty = express_balances.get(item.express_sku, 0)
            
            # Only include if there's stock in either system or they mismatch
            if django_qty != 0 or express_qty != 0:
                results.append({
                    'item': item,
                    'django_qty': django_qty,
                    'express_qty': express_qty,
                    'variance': django_qty - express_qty,
                    'is_match': django_qty == express_qty
                })
        
        return results
