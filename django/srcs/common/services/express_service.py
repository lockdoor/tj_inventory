import requests
from django.conf import settings
from common.models import Company


class ExpressHelperService:
    """
    Helper service for connecting and communicating with Express ERP FastAPI Bridge.
    Globally accessible across all system modules.
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
            location = ExpressHelperService.get_express_location()
            if not location:
                return False
            response = requests.get(location, timeout=5)
            if response.status_code != 200:
                raise Exception(f"Express Bridge returned error {response.status_code}: {response.text}")
            return True
        except Exception:
            return False

    @staticmethod
    def get_companies():
        """Get companies from database."""
        return list(Company.objects.filter(is_deleted=False).values_list('express_database_name', flat=True))
