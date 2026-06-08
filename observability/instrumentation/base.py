"""
Base instrumentation for AutoDeal IA Hunter.
"""
from abc import ABC, abstractmethod


class BaseInstrumentation(ABC):
    """Base class for instrumentation."""
    
    @abstractmethod
    def setup(self) -> None:
        """Setup instrumentation."""
        pass
    
    @abstractmethod
    def teardown(self) -> None:
        """Teardown instrumentation."""
        pass
