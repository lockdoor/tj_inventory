import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from common.models import Individual


@pytest.fixture
def user(db):
    return User.objects.create_user("john_doe", "john@test.com", "pass")


@pytest.mark.django_db
class TestIndividualModel:
    """
    Tests verifying validation, normalizations, and relationship constraints 
    on the Individual model.
    """

    def test_individual_creation_and_normalizations(self, user):
        ind = Individual.objects.create(
            first_name="  John  ",
            last_name="  Doe  ",
            email="  JOHN@test.com  ",
            phones=["+6621234567", "+66898765432"],
            created_by=user
        )
        
        # Verify names are trimmed
        assert ind.first_name == "John"
        assert ind.last_name == "Doe"
        
        # Verify email is trimmed and converted to lowercase
        assert ind.email == "john@test.com"
        
        # Verify string conversion
        assert str(ind) == "John Doe"
        
        # Verify phones JSONField lists are stored correctly
        assert isinstance(ind.phones, list)
        assert len(ind.phones) == 2
        assert ind.phones[0] == "+6621234567"

    def test_optional_user_relationship(self, user):
        # Create an individual with no linked User (e.g. personal customer or non-login employee)
        ind_no_user = Individual.objects.create(
            first_name="Alice",
            last_name="Smith",
            created_by=user
        )
        assert ind_no_user.user is None

        # Create an individual linked to a User credentials record
        ind_with_user = Individual.objects.create(
            first_name="Bob",
            last_name="Builder",
            user=user,
            created_by=user
        )
        assert ind_with_user.user == user
        assert user.individual == ind_with_user

    def test_phones_normalization_to_list(self, user):
        # If phones is set to None or an invalid type, save() should fallback to empty list
        ind = Individual.objects.create(
            first_name="Test",
            last_name="Person",
            phones="not a list",
            created_by=user
        )
        assert ind.phones == []
