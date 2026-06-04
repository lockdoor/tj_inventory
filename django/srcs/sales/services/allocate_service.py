from common.interfaces import SourcingAllocationSource
from sales.models import SalesAllocation

class AllocateService:

    @staticmethod
    def get_reservation(allocation: SalesAllocation) -> SourcingAllocationSource:
        """
        Polymorphically retrieves the underlying reservation using the new property.
        """
        return allocation.reservation

    @staticmethod
    def release(allocation: SalesAllocation, user=None):
        """
        Releases the reservation associated with this allocation.
        """
        res = AllocateService.get_reservation(allocation)
        if res:
            res.release(user=user)