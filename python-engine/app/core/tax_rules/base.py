"""
Base interface for tax rule modules.
Each tax category (VAT, CIT, PIT, ...) implements this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class CustomerType(str, Enum):
    SME = "sme"
    HOUSEHOLD = "household"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


class TaxCategory(str, Enum):
    VAT = "vat"
    CIT = "cit"  # Corporate Income Tax - Thuế TNDN
    PIT = "pit"  # Personal Income Tax - Thuế TNCN
    LICENSE = "license"  # Thuế môn bài
    SPECIAL_CONSUMPTION = "special_consumption"
    IMPORT_EXPORT = "import_export"
    ENVIRONMENT = "environment"


@dataclass
class TaxContext:
    """Context for tax calculation / consultation."""

    customer_type: CustomerType = CustomerType.UNKNOWN
    revenue: float | None = None  # Doanh thu
    income: float | None = None  # Thu nhập
    industry_code: str | None = None  # Mã ngành nghề
    province: str | None = None  # Tỉnh/thành phố
    year: int | None = None
    quarter: int | None = None
    extra: dict = field(default_factory=dict)


@dataclass
class TaxResult:
    """Result from a tax rule calculation."""

    category: TaxCategory
    amount: float | None = None
    rate: float | None = None
    explanation: str = ""
    legal_basis: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class TaxRule(ABC):
    """Base class for tax rule implementations."""

    @property
    @abstractmethod
    def category(self) -> TaxCategory:
        ...

    @abstractmethod
    def calculate(self, context: TaxContext) -> TaxResult:
        """Calculate tax based on context."""
        ...

    @abstractmethod
    def get_info(self, customer_type: CustomerType) -> str:
        """Return general information about this tax type for the given customer."""
        ...

    def get_consultation(
        self, customer_type: CustomerType, entities: dict | None = None,
    ) -> str:
        """Return a detailed consultation response, contextualised by entities.

        Override in subclasses to provide richer, situation-aware advice.
        Falls back to ``get_info`` when not overridden.
        """
        return self.get_info(customer_type)
