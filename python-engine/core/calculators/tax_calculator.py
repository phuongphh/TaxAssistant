"""
Tax Calculator - pure tax calculation coordination.

Routes calculation requests to the appropriate tax rule implementation.
No LLM or external service dependencies.
"""

import logging

from core.tax_rules.base import CustomerType, TaxCategory, TaxContext, TaxResult
from core.tax_rules.cit import CITRule
from core.tax_rules.license_tax import LicenseTaxRule
from core.tax_rules.pit import PITRule
from core.tax_rules.vat import VATRule

logger = logging.getLogger(__name__)


class TaxCalculator:
    """Routes tax calculation requests to appropriate tax rule implementations.

    Pure domain logic: no LLM, no external services, no I/O.
    Can run standalone for CLI testing and unit tests.
    """

    def __init__(self) -> None:
        self.rules: dict[TaxCategory, object] = {
            TaxCategory.VAT: VATRule(),
            TaxCategory.CIT: CITRule(),
            TaxCategory.PIT: PITRule(),
            TaxCategory.LICENSE: LicenseTaxRule(),
        }

    def calculate(
        self,
        category: TaxCategory,
        customer_type: CustomerType = CustomerType.UNKNOWN,
        revenue: float | None = None,
        income: float | None = None,
        industry_code: str | None = None,
        province: str | None = None,
        extra: dict | None = None,
    ) -> TaxResult | None:
        """Calculate tax for a given category and context.

        Returns None if the category has no registered rule.
        """
        rule = self.rules.get(category)
        if not rule:
            logger.warning("No rule registered for category: %s", category)
            return None

        context = TaxContext(
            customer_type=customer_type,
            revenue=revenue,
            income=income,
            industry_code=industry_code,
            province=province,
            extra=extra or {},
        )
        result = rule.calculate(context)
        logger.debug(
            "Calculated %s: amount=%s rate=%s customer_type=%s",
            category.value, result.amount, result.rate, customer_type.value,
        )
        return result

    def get_info(self, category: TaxCategory, customer_type: CustomerType = CustomerType.UNKNOWN) -> str | None:
        """Get general information about a tax category for the given customer type."""
        rule = self.rules.get(category)
        if not rule:
            return None
        return rule.get_info(customer_type)

    @property
    def supported_categories(self) -> list[TaxCategory]:
        """List of supported tax categories."""
        return list(self.rules.keys())
