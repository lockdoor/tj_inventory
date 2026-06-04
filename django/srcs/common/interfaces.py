from typing import Protocol, Optional
from decimal import Decimal
from django.contrib.auth.models import User
from catalog.models import Item

class SourcingAllocationSource(Protocol):
    """
    Interface/Protocol for all sourcing allocation sources:
    StockReservation, ArrivalReservation, and Shortage.
    """
    @property
    def allocated_quantity(self) -> Decimal:
        """Returns the quantity allocated/requested."""
        ...

    @property
    def document_reference(self) -> str:
        """Returns the reference document number or ID."""
        ...

    @property
    def source_item(self) -> Item:
        """Returns the catalog Item associated with this allocation."""
        ...

    def release(self, user: Optional[User] = None) -> bool:
        """Releases the allocation hold or cancels/deletes the record."""
        ...
