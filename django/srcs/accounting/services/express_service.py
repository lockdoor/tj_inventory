from django.core.exceptions import ValidationError
from common.services import ExpressHelperService
from accounting.services import PettyCashCategoryService
from common.models import Company
import requests

class ExpressService:
    """
    Service for integrating with Express ERP via a FastAPI Bridge.
    """

    @staticmethod
    def update_category_from_express(company: Company, created_by):
        """
        Create or Update PettyCashCategory from Express
        """
        url = ExpressHelperService.get_express_location() + '/account/' + company.express_database_name + '/account-chart'

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                # change key ACCNUM to code and ACCNAM to name
                data = response.json()
                categories_data = [
                    {
                        'code': account['ACCNUM'],
                        'name': account['ACCNAM']
                    }
                    for account in data
                    if account.get('ACCNUM') and account.get('ACCNAM')
                ] 
                return PettyCashCategoryService.bulk_create_or_update_categories(categories_data=categories_data, company=company, created_by=created_by)
            else:
                raise ValidationError(f"Failed to fetch data from Express: {response.status_code}")
        except Exception as e:
            raise ValidationError(f"Failed to fetch data from Express: {e}")

        