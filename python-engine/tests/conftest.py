"""
Shared test fixtures for Tax Assistant test suite.
"""

import pytest

from app.core.intent_classifier import IntentClassifier
from app.core.tax_engine import TaxEngine
from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from app.core.tax_rules.vat import VATRule
from app.core.tax_rules.cit import CITRule
from app.core.tax_rules.pit import PITRule
from app.core.tax_rules.license_tax import LicenseTaxRule


# ---------------------------------------------------------------------------
# Tax Rule fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vat_rule() -> VATRule:
    return VATRule()


@pytest.fixture
def cit_rule() -> CITRule:
    return CITRule()


@pytest.fixture
def pit_rule() -> PITRule:
    return PITRule()


@pytest.fixture
def license_tax_rule() -> LicenseTaxRule:
    return LicenseTaxRule()


# ---------------------------------------------------------------------------
# Classifier & Engine fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


@pytest.fixture
def tax_engine() -> TaxEngine:
    """TaxEngine without RAG (rule-based only)."""
    return TaxEngine()


# ---------------------------------------------------------------------------
# Context helper fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sme_context():
    """Factory for creating SME tax contexts."""
    def _make(revenue: float | None = None, income: float | None = None, **extra):
        return TaxContext(
            customer_type=CustomerType.SME,
            revenue=revenue,
            income=income,
            extra=extra,
        )
    return _make


@pytest.fixture
def household_context():
    """Factory for creating Household tax contexts."""
    def _make(revenue: float | None = None, income: float | None = None, **extra):
        return TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=revenue,
            income=income,
            extra=extra,
        )
    return _make


@pytest.fixture
def individual_context():
    """Factory for creating Individual tax contexts."""
    def _make(revenue: float | None = None, income: float | None = None, **extra):
        return TaxContext(
            customer_type=CustomerType.INDIVIDUAL,
            revenue=revenue,
            income=income,
            extra=extra,
        )
    return _make
