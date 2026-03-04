"""
Intent classifier for Vietnamese tax queries.
Classifies user messages into actionable intents + tax categories.
Integrates Vietnamese NLP for text normalization and entity extraction.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from app.core.tax_rules.base import TaxCategory

logger = logging.getLogger(__name__)


class Intent(str, Enum):
    # Tax information / consultation
    TAX_INFO = "tax_info"  # Hỏi thông tin chung về thuế
    TAX_CALCULATE = "tax_calculate"  # Yêu cầu tính thuế
    TAX_DEADLINE = "tax_deadline"  # Hỏi hạn nộp thuế
    TAX_PROCEDURE = "tax_procedure"  # Hỏi thủ tục, quy trình

    # Document related
    DOCUMENT_CHECK = "document_check"  # Kiểm tra hóa đơn, chứng từ
    DOCUMENT_UPLOAD = "document_upload"  # Upload tài liệu

    # Registration / Declaration
    REGISTRATION = "registration"  # Đăng ký thuế
    DECLARATION = "declaration"  # Kê khai thuế

    # Penalties / Issues
    PENALTY = "penalty"  # Phạt, vi phạm thuế
    DISPUTE = "dispute"  # Khiếu nại, tranh chấp

    # General
    GREETING = "greeting"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ClassificationResult:
    intent: Intent
    tax_category: TaxCategory | None
    confidence: float
    extracted_entities: dict


# Keyword patterns for rule-based classification (supplemented by LLM)
_INTENT_PATTERNS: list[tuple[Intent, list[str]]] = [
    (Intent.TAX_CALCULATE, [
        r"tính thuế", r"thuế phải nộp", r"bao nhiêu thuế", r"mức thuế",
        r"tính .+ thuế", r"thuế bao nhiêu",
    ]),
    (Intent.TAX_INFO, [
        r"thuế .+ là gì", r"thông tin .+ thuế", r"thông tin thuế",
        r"thuế suất", r"quy định .+ thuế", r"luật thuế", r"nghị định",
        r"về thuế", r"thuế gtgt\b", r"thuế tndn\b", r"thuế tncn\b",
        r"tra cứu",
    ]),
    (Intent.TAX_DEADLINE, [
        r"hạn nộp", r"thời hạn", r"deadline", r"khi nào nộp",
        r"nộp trước ngày", r"hạn kê khai",
    ]),
    (Intent.TAX_PROCEDURE, [
        r"thủ tục", r"quy trình", r"cách .+ nộp", r"hướng dẫn",
        r"làm sao", r"cần gì để", r"cần những gì",
        r"quy trình.*kê khai", r"quy trình.*nộp thuế", r"quy trình.*đăng ký",
        r"thủ tục.*kê khai", r"thủ tục.*nộp thuế",
    ]),
    (Intent.DOCUMENT_CHECK, [
        r"hóa đơn", r"chứng từ", r"hợp lệ", r"kiểm tra",
        r"xác minh", r"invoice",
    ]),
    (Intent.DECLARATION, [
        r"kê khai", r"tờ khai", r"báo cáo thuế", r"quyết toán",
        r"mẫu .+ kê khai",
    ]),
    (Intent.REGISTRATION, [
        r"đăng ký thuế", r"mã số thuế", r"MST", r"cấp MST",
    ]),
    (Intent.PENALTY, [
        r"phạt", r"vi phạm", r"chậm nộp", r"trốn thuế",
        r"xử phạt", r"tiền phạt",
    ]),
    (Intent.GREETING, [
        r"^(xin )?chào", r"^hello", r"^hi\b", r"^hey",
    ]),
    (Intent.HELP, [
        r"giúp", r"hỗ trợ", r"help", r"trợ giúp", r"hướng dẫn sử dụng",
    ]),
]

_CATEGORY_PATTERNS: list[tuple[TaxCategory, list[str]]] = [
    (TaxCategory.VAT, [
        r"gtgt", r"giá trị gia tăng", r"vat", r"thuế đầu vào", r"thuế đầu ra",
    ]),
    (TaxCategory.CIT, [
        r"tndn", r"thu nhập doanh nghiệp", r"corporate", r"lợi nhuận",
    ]),
    (TaxCategory.PIT, [
        r"tncn", r"thu nhập cá nhân", r"personal", r"lương", r"tiền công",
        r"giảm trừ gia cảnh", r"người phụ thuộc",
    ]),
    (TaxCategory.LICENSE, [
        r"môn bài", r"license", r"lệ phí môn bài",
    ]),
]


class IntentClassifier:
    """
    Hybrid intent classifier:
    - Rule-based keyword matching for fast, deterministic results
    - Vietnamese NLP integration for text normalization and entity extraction
    - Falls back to LLM classification for ambiguous cases
    """

    def __init__(self) -> None:
        self._nlp = None
        try:
            from app.nlp.vietnamese import VietnameseNLP
            self._nlp = VietnameseNLP()
            logger.info("Vietnamese NLP module loaded")
        except Exception:
            logger.info("Vietnamese NLP module unavailable, using basic processing")

    def classify(self, text: str) -> ClassificationResult:
        """Classify user message intent using keyword patterns."""
        text_lower = text.lower().strip()

        # Detect intent
        intent = Intent.UNKNOWN
        best_score = 0.0

        for candidate_intent, patterns in _INTENT_PATTERNS:
            score = self._match_patterns(text_lower, patterns)
            if score > best_score:
                best_score = score
                intent = candidate_intent

        # Detect tax category
        tax_category = None
        for candidate_cat, patterns in _CATEGORY_PATTERNS:
            if self._match_patterns(text_lower, patterns) > 0:
                tax_category = candidate_cat
                break

        # Extract numeric entities
        entities = self._extract_entities(text_lower)

        # Normalize confidence: 1 match → 0.6, 2 → 0.75, 3+ → 0.85+
        confidence = min(0.5 + best_score * 0.15, 0.95) if intent != Intent.UNKNOWN else 0.3

        return ClassificationResult(
            intent=intent,
            tax_category=tax_category,
            confidence=confidence,
            extracted_entities=entities,
        )

    def _match_patterns(self, text: str, patterns: list[str]) -> float:
        """Score how well patterns match the text.

        Uses absolute match count (not normalized by total patterns) so that
        intents with more patterns aren't penalised.  Compound patterns
        (e.g. "quy trình.*kê khai") score 2 points to give them priority
        over single-keyword matches across different intents.
        """
        score = 0.0
        for p in patterns:
            if re.search(p, text):
                # Compound patterns (containing ".*") indicate a stronger
                # multi-keyword signal and deserve extra weight.
                score += 2.0 if ".*" in p else 1.0
        return score

    def _extract_entities(self, text: str) -> dict:
        """Extract numeric entities from text (revenue, income, etc.)."""
        entities: dict = {}

        # Use NLP module for richer extraction if available
        if self._nlp:
            amounts = self._nlp.extract_money_amounts(text)
            if amounts:
                entities["amount"] = amounts[0]["value"]

            doc_refs = self._nlp.extract_tax_document_refs(text)
            if doc_refs:
                entities["document_refs"] = [r["full_ref"] for r in doc_refs]
        else:
            # Fallback: basic regex extraction
            money_patterns = [
                (r"(\d+(?:[.,]\d+)?)\s*tỷ", 1_000_000_000),
                (r"(\d+(?:[.,]\d+)?)\s*triệu", 1_000_000),
                (r"(\d+(?:[.,]\d+)?)\s*nghìn", 1_000),
                (r"(\d{6,})", 1),  # Raw number >= 6 digits
            ]

            for pattern, multiplier in money_patterns:
                match = re.search(pattern, text)
                if match:
                    value = float(match.group(1).replace(",", "."))
                    entities["amount"] = value * multiplier
                    break

        # Extract number of dependents (always use regex, NLP doesn't handle this)
        dep_match = re.search(r"(\d+)\s*người phụ thuộc", text)
        if dep_match:
            entities["dependents"] = int(dep_match.group(1))

        return entities
