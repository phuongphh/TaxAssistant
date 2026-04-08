"""
Tax configuration loader.

Loads tax parameters (deductions, brackets, rates) from tax_config.json.
This allows tax rules to be updated without code changes - just update
the JSON file and restart (or trigger a hot-reload).

Usage:
    from data.tax_config_loader import tax_config

    deduction = tax_config.pit_personal_deduction
    brackets = tax_config.pit_brackets
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent / "tax_config.json"


class TaxConfig:
    """Loaded tax configuration with sensible defaults."""

    def __init__(self) -> None:
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        """Load or reload tax config from JSON file."""
        if not CONFIG_PATH.exists():
            logger.warning("tax_config.json not found, using hardcoded defaults")
            self._data = {}
            return

        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                self._data = json.load(f)
            logger.info("Loaded tax config from %s", CONFIG_PATH)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to load tax_config.json: %s", e)
            self._data = {}

    # --- PIT ---
    @property
    def pit_personal_deduction(self) -> int:
        return self._data.get("pit", {}).get("personal_deduction", 15_500_000)

    @property
    def pit_dependent_deduction(self) -> int:
        return self._data.get("pit", {}).get("dependent_deduction", 6_200_000)

    @property
    def pit_brackets(self) -> list[tuple[float, float]]:
        """Return PIT brackets as list of (limit, rate) tuples."""
        raw = self._data.get("pit", {}).get("brackets")
        if not raw:
            return [
                (10_000_000, 0.05),
                (30_000_000, 0.10),
                (60_000_000, 0.20),
                (100_000_000, 0.30),
                (float("inf"), 0.35),
            ]
        return [
            (b["limit"] if b["limit"] is not None else float("inf"), b["rate"])
            for b in raw
        ]

    @property
    def pit_legal_basis(self) -> list[str]:
        return self._data.get("pit", {}).get("legal_basis", [
            "Luật Thuế TNCN số 109/2025/QH15",
            "Nghị quyết 110/2025/UBTVQH15",
            "Thông tư 111/2013/TT-BTC",
        ])

    # --- VAT ---
    @property
    def vat_rate_standard(self) -> float:
        return self._data.get("vat", {}).get("rate_standard", 0.10)

    @property
    def vat_rate_reduced(self) -> float:
        return self._data.get("vat", {}).get("rate_reduced", 0.05)

    @property
    def vat_rate_special_reduced(self) -> float:
        return self._data.get("vat", {}).get("rate_special_reduced", 0.08)

    @property
    def vat_registration_threshold(self) -> int:
        return self._data.get("vat", {}).get("registration_threshold", 100_000_000)

    # --- CIT ---
    @property
    def cit_rate_standard(self) -> float:
        return self._data.get("cit", {}).get("rate_standard", 0.20)

    @property
    def cit_rate_small(self) -> float:
        return self._data.get("cit", {}).get("rate_small", 0.17)

    @property
    def last_updated(self) -> str:
        return self._data.get("_last_updated", "unknown")

    @property
    def legal_basis(self) -> str:
        return self._data.get("_legal_basis", "")


# Singleton instance
tax_config = TaxConfig()
