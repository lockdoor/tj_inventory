from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from inventory.models import Stock
from django.db.models import Sum

class AvailableLotsAPIView(LoginRequiredMixin, View):
    """
    API endpoint to fetch available lots and their balances
    for a given warehouse and item.
    """
    def get(self, request, *args, **kwargs):
        warehouse_id = request.GET.get('warehouse_id')
        item_id = request.GET.get('item_id')

        if not warehouse_id or not item_id:
            return JsonResponse({'error': 'Missing warehouse_id or item_id'}, status=400)

        try:
            stocks = Stock.objects.filter(
                warehouse_id=warehouse_id,
                item_id=item_id,
                balance__gt=0
            ).values('lot_number').annotate(total_balance=Sum('balance'))
            
            lots = [
                {
                    'lot_number': stock['lot_number'],
                    'balance': float(stock['total_balance'])
                }
                for stock in stocks
            ]
            
            return JsonResponse({'lots': lots})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
