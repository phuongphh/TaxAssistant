"""
Unit tests for IntentClassifier.
Tests intent detection, tax category detection, and entity extraction.
"""

import pytest

from core.intent_classifier import IntentClassifier, Intent
from core.tax_rules.base import TaxCategory


@pytest.fixture
def classifier():
    return IntentClassifier()


class TestIntentDetection:
    """Test that Vietnamese tax queries are classified to correct intents."""

    # --- TAX_CALCULATE ---
    @pytest.mark.parametrize("text", [
        "tính thuế GTGT doanh thu 500 triệu",
        "thuế phải nộp bao nhiêu",
        "mức thuế TNDN là bao nhiêu",
        "tính thuế TNCN lương 30 triệu",
        "thuế bao nhiêu cho 1 tỷ doanh thu",
    ])
    def test_tax_calculate_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.TAX_CALCULATE

    # --- TAX_INFO ---
    @pytest.mark.parametrize("text", [
        "thuế GTGT là gì",
        "thông tin về thuế TNDN",
        "thuế suất hiện tại",
        "quy định về thuế môn bài",
        "luật thuế thu nhập cá nhân",
    ])
    def test_tax_info_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.TAX_INFO

    # --- TAX_DEADLINE ---
    @pytest.mark.parametrize("text", [
        "hạn nộp thuế GTGT quý 1",
        "thời hạn kê khai thuế",
        "khi nào nộp thuế TNDN",
        "deadline nộp thuế",
        "nộp trước ngày nào quý 2",
    ])
    def test_tax_deadline_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.TAX_DEADLINE

    # --- TAX_PROCEDURE ---
    @pytest.mark.parametrize("text", [
        "thủ tục nộp thuế GTGT",
        "quy trình nộp thuế",
        "hướng dẫn cách nộp thuế",
        "làm sao nộp thuế online",
        "cần những gì để nộp thuế",
    ])
    def test_tax_procedure_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.TAX_PROCEDURE

    # --- DECLARATION ---
    @pytest.mark.parametrize("text", [
        "kê khai thuế quý 1",
        "tờ khai thuế GTGT",
        "quyết toán thuế năm 2024",
        "mẫu 01 kê khai GTGT",
    ])
    def test_declaration_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.DECLARATION

    # --- PENALTY ---
    @pytest.mark.parametrize("text", [
        "phạt chậm nộp thuế",
        "vi phạm thuế bị xử lý thế nào",
        "tiền phạt nộp chậm",
        "trốn thuế bị phạt bao nhiêu",
    ])
    def test_penalty_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.PENALTY

    # --- GREETING ---
    @pytest.mark.parametrize("text", [
        "xin chào",
        "chào bạn",
        "hello",
        "hi",
        "hey",
    ])
    def test_greeting_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.GREETING

    # --- HELP ---
    @pytest.mark.parametrize("text", [
        "giúp tôi với",
        "hỗ trợ",
        "help",
        "hướng dẫn sử dụng",
    ])
    def test_help_intent(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == Intent.HELP

    # --- UNKNOWN ---
    def test_unknown_intent(self, classifier: IntentClassifier):
        result = classifier.classify("thời tiết hôm nay thế nào")
        assert result.intent == Intent.UNKNOWN
        assert result.confidence == 0.3


class TestTaxCategoryDetection:
    """Test that tax category is correctly identified from message."""

    @pytest.mark.parametrize("text,expected", [
        ("thuế GTGT doanh thu 500 triệu", TaxCategory.VAT),
        ("thuế giá trị gia tăng", TaxCategory.VAT),
        ("VAT rate", TaxCategory.VAT),
        ("thuế đầu vào đầu ra", TaxCategory.VAT),
    ])
    def test_vat_detection(self, classifier: IntentClassifier, text: str, expected: TaxCategory):
        result = classifier.classify(text)
        assert result.tax_category == expected

    @pytest.mark.parametrize("text,expected", [
        ("thuế TNDN năm 2024", TaxCategory.CIT),
        ("thuế thu nhập doanh nghiệp", TaxCategory.CIT),
        ("lợi nhuận chịu thuế", TaxCategory.CIT),
    ])
    def test_cit_detection(self, classifier: IntentClassifier, text: str, expected: TaxCategory):
        result = classifier.classify(text)
        assert result.tax_category == expected

    @pytest.mark.parametrize("text,expected", [
        ("thuế TNCN lương 30 triệu", TaxCategory.PIT),
        ("thuế thu nhập cá nhân", TaxCategory.PIT),
        ("giảm trừ gia cảnh", TaxCategory.PIT),
        ("2 người phụ thuộc", TaxCategory.PIT),
    ])
    def test_pit_detection(self, classifier: IntentClassifier, text: str, expected: TaxCategory):
        result = classifier.classify(text)
        assert result.tax_category == expected

    @pytest.mark.parametrize("text,expected", [
        ("thuế môn bài", TaxCategory.LICENSE),
        ("lệ phí môn bài năm 2024", TaxCategory.LICENSE),
    ])
    def test_license_detection(self, classifier: IntentClassifier, text: str, expected: TaxCategory):
        result = classifier.classify(text)
        assert result.tax_category == expected

    def test_no_category_for_general_query(self, classifier: IntentClassifier):
        result = classifier.classify("tính thuế cho tôi")
        assert result.tax_category is None


class TestEntityExtraction:
    """Test extraction of numeric entities from Vietnamese text."""

    def test_extract_billion(self, classifier: IntentClassifier):
        result = classifier.classify("doanh thu 1.5 tỷ")
        assert result.extracted_entities.get("amount") == 1_500_000_000

    def test_extract_million(self, classifier: IntentClassifier):
        result = classifier.classify("lương 30 triệu")
        assert result.extracted_entities.get("amount") == 30_000_000

    def test_extract_500_million(self, classifier: IntentClassifier):
        result = classifier.classify("doanh thu 500 triệu")
        assert result.extracted_entities.get("amount") == 500_000_000

    def test_extract_thousand(self, classifier: IntentClassifier):
        result = classifier.classify("phí 200 nghìn")
        assert result.extracted_entities.get("amount") == 200_000

    def test_extract_raw_number(self, classifier: IntentClassifier):
        result = classifier.classify("doanh thu 500000000")
        assert result.extracted_entities.get("amount") == 500_000_000

    def test_extract_dependents(self, classifier: IntentClassifier):
        result = classifier.classify("thuế TNCN lương 30 triệu 2 người phụ thuộc")
        assert result.extracted_entities.get("dependents") == 2
        assert result.extracted_entities.get("amount") == 30_000_000

    def test_no_entities_for_plain_text(self, classifier: IntentClassifier):
        result = classifier.classify("thuế GTGT là gì")
        assert "amount" not in result.extracted_entities

    def test_billion_with_comma(self, classifier: IntentClassifier):
        result = classifier.classify("doanh thu 2,5 tỷ")
        assert result.extracted_entities.get("amount") == 2_500_000_000


class TestConfidenceScoring:
    def test_strong_match_has_high_confidence(self, classifier: IntentClassifier):
        result = classifier.classify("tính thuế GTGT doanh thu 500 triệu thuế bao nhiêu")
        assert result.confidence > 0.3

    def test_greeting_has_positive_confidence(self, classifier: IntentClassifier):
        result = classifier.classify("xin chào")
        assert result.confidence > 0

    def test_unknown_has_low_confidence(self, classifier: IntentClassifier):
        result = classifier.classify("abc xyz random text")
        assert result.confidence == 0.3
