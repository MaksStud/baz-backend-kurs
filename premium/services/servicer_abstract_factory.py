from abc import ABC, abstractmethod
import datetime


class CompanyPaymentValidateAbstract(ABC):
    """An abstract class for payment validation services."""

    @abstractmethod
    def end_date(self, *args, **kwargs) -> datetime:
        """Returns the time until which the subscription should be valid. Must be a primary value."""
        raise NotImplementedError("This method is overridden in derived classes.")
