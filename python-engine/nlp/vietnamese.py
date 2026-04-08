"""
Vietnamese NLP processing utilities.
Uses underthesea for tokenization, POS tagging, and NER.
"""

import logging
import re

from underthesea import word_tokenize, pos_tag, ner, classify

logger = logging.getLogger(__name__)


class VietnameseNLP:
    """Vietnamese NLP processor for tax-related text."""

    # Tax-specific abbreviations and their expansions
    TAX_ABBREVIATIONS: dict[str, str] = {
        "GTGT": "giá trị gia tăng",
        "TNDN": "thu nhập doanh nghiệp",
        "TNCN": "thu nhập cá nhân",
        "MST": "mã số thuế",
        "HĐGTGT": "hóa đơn giá trị gia tăng",
        "DN": "doanh nghiệp",
        "BHXH": "bảo hiểm xã hội",
        "BHYT": "bảo hiểm y tế",
        "BHTN": "bảo hiểm thất nghiệp",
        "NĐ": "nghị định",
        "TT": "thông tư",
        "QĐ": "quyết định",
        "NQ": "nghị quyết",
        "CP": "chính phủ",
        "BTC": "bộ tài chính",
        "TCT": "tổng cục thuế",
        "DT": "doanh thu",
        "TSCĐ": "tài sản cố định",
        "CCDC": "công cụ dụng cụ",
    }

    def tokenize(self, text: str) -> list[str]:
        """Word segmentation for Vietnamese text."""
        return word_tokenize(text, format="list")

    def pos_tagging(self, text: str) -> list[tuple[str, str]]:
        """Part-of-speech tagging."""
        return pos_tag(text)

    def named_entities(self, text: str) -> list[tuple[str, str, str, str]]:
        """Named Entity Recognition - extract organizations, amounts, dates, etc."""
        return ner(text)

    def normalize_tax_text(self, text: str) -> str:
        """
        Normalize Vietnamese tax-related text:
        - Expand abbreviations
        - Normalize numbers
        - Clean whitespace
        """
        normalized = text.strip()

        # Expand common tax abbreviations for better NLP processing
        for abbr, expansion in self.TAX_ABBREVIATIONS.items():
            # Match abbreviation as whole word (case insensitive)
            pattern = rf"\b{re.escape(abbr)}\b"
            normalized = re.sub(pattern, f"{abbr} ({expansion})", normalized, count=1)

        # Normalize Vietnamese number formats
        # "1.000.000" → "1000000" for processing
        normalized = re.sub(r"(\d)\.(\d{3})(?=\.|$|\s)", r"\1\2", normalized)

        return normalized

    def extract_money_amounts(self, text: str) -> list[dict]:
        """Extract monetary amounts from Vietnamese text."""
        amounts = []

        patterns = [
            (r"(\d+(?:[.,]\d+)?)\s*tỷ(?:\s*đồng)?", 1_000_000_000),
            (r"(\d+(?:[.,]\d+)?)\s*triệu(?:\s*đồng)?", 1_000_000),
            (r"(\d+(?:[.,]\d+)?)\s*nghìn(?:\s*đồng)?", 1_000),
            (r"(\d+(?:[.,]\d+)?)\s*(?:đồng|VND|vnđ)", 1),
            (r"(\d{7,})", 1),  # Large raw numbers (>= 10 million)
        ]

        for pattern, multiplier in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                value_str = match.group(1).replace(",", ".").replace(".", "", match.group(1).count(".") - 1)
                try:
                    value = float(value_str) * multiplier
                    amounts.append({
                        "value": value,
                        "raw": match.group(0),
                        "position": match.start(),
                    })
                except ValueError:
                    continue

        return amounts

    def extract_tax_document_refs(self, text: str) -> list[dict]:
        """Extract references to Vietnamese tax documents (laws, decrees, circulars)."""
        refs = []

        # Pattern for Vietnamese legal document numbers
        # e.g., "Nghị định 123/2020/NĐ-CP", "Thông tư 78/2014/TT-BTC"
        pattern = r"((?:Luật|Nghị định|Thông tư|Quyết định|Nghị quyết)\s+(?:số\s+)?(\d+/\d{4}/[\w-]+))"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            refs.append({
                "full_ref": match.group(1),
                "number": match.group(2),
                "position": match.start(),
            })

        return refs
