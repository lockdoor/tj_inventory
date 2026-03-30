import pytest
import django
from django.conf import settings


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """Automatically give all tests database access."""
    pass
