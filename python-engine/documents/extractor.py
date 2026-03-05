"""
Data extraction from OCR'd tax documents.
Pattern-based extraction for Vietnamese tax invoices and receipts.
"""

import re


class DataExtractor:
    """Extract structured data from OCR text of Vietnamese tax documents."""

    def extract_invoice(self, text: str) -> dict:
        """
        Extract fields from a Vietnamese VAT invoice (Hóa đơn GTGT).
        Fields: invoice number, date, seller/buyer info, amounts, VAT.
        """
        data: dict = {}

        # Số hóa đơn
        inv_match = re.search(r"(?:Số|No\.?)[:\s]*(\d{7,})", text)
        if inv_match:
            data["invoice_number"] = inv_match.group(1)

        # Ký hiệu (Series)
        series_match = re.search(r"(?:Ký hiệu|Serial)[:\s]*([A-Z0-9/]+)", text, re.IGNORECASE)
        if series_match:
            data["invoice_series"] = series_match.group(1)

        # Ngày (Date)
        date_match = re.search(r"(?:Ngày|Date)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", text)
        if date_match:
            data["invoice_date"] = date_match.group(1)

        # MST người bán (Seller tax code)
        seller_tax = re.search(r"(?:MST|Mã số thuế).*?(\d{10,14})", text)
        if seller_tax:
            data["seller_tax_code"] = seller_tax.group(1)
            data["tax_code"] = seller_tax.group(1)

        # Tên người bán
        seller_name = re.search(
            r"(?:Đơn vị bán|Người bán|Seller|Tên công ty)[:\s]*(.+?)(?:\n|$)",
            text, re.IGNORECASE,
        )
        if seller_name:
            data["seller_name"] = seller_name.group(1).strip()

        # Tên người mua
        buyer_name = re.search(
            r"(?:Người mua|Buyer|Tên đơn vị mua)[:\s]*(.+?)(?:\n|$)",
            text, re.IGNORECASE,
        )
        if buyer_name:
            data["buyer_name"] = buyer_name.group(1).strip()

        # MST người mua
        buyer_tax = re.search(
            r"(?:MST.*?mua|Mã số thuế.*?mua).*?(\d{10,14})", text, re.IGNORECASE,
        )
        if buyer_tax:
            data["buyer_tax_code"] = buyer_tax.group(1)

        # Amounts
        data.update(self._extract_amounts(text))

        return data

    def extract_receipt(self, text: str) -> dict:
        """Extract data from a payment receipt / phiếu thu."""
        data: dict = {}

        # Date
        date_match = re.search(r"(?:Ngày|Date)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})", text)
        if date_match:
            data["date"] = date_match.group(1)

        # Amount
        data.update(self._extract_amounts(text))

        # MST
        tax_match = re.search(r"(\d{10,14})", text)
        if tax_match:
            data["tax_code"] = tax_match.group(1)

        return data

    def extract_generic(self, text: str) -> dict:
        """Generic extraction for unknown document types."""
        data: dict = {}

        # Try to extract any tax codes
        tax_codes = re.findall(r"\b(\d{10}(?:-\d{3})?)\b", text)
        if tax_codes:
            data["tax_codes_found"] = list(set(tax_codes))

        # Extract dates
        dates = re.findall(r"\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}", text)
        if dates:
            data["dates_found"] = dates

        # Extract amounts
        data.update(self._extract_amounts(text))

        return data

    def _extract_amounts(self, text: str) -> dict:
        """Extract monetary amounts from invoice text."""
        amounts: dict = {}

        # Tiền hàng (Subtotal)
        subtotal = re.search(
            r"(?:Cộng tiền hàng|Tiền hàng|Subtotal)[:\s]*([\d.,]+)",
            text, re.IGNORECASE,
        )
        if subtotal:
            amounts["subtotal"] = self._parse_amount(subtotal.group(1))

        # Thuế suất VAT
        vat_rate = re.search(r"(?:Thuế suất|VAT)[:\s]*(\d+)\s*%", text, re.IGNORECASE)
        if vat_rate:
            amounts["vat_rate"] = f"{vat_rate.group(1)}%"

        # Tiền thuế GTGT
        vat_amount = re.search(
            r"(?:Tiền thuế|VAT amount|Thuế GTGT)[:\s]*([\d.,]+)",
            text, re.IGNORECASE,
        )
        if vat_amount:
            amounts["vat_amount"] = self._parse_amount(vat_amount.group(1))

        # Tổng cộng (Total)
        total = re.search(
            r"(?:Tổng (?:cộng )?(?:tiền )?thanh toán|Grand total|Total)[:\s]*([\d.,]+)",
            text, re.IGNORECASE,
        )
        if total:
            amounts["total_amount"] = self._parse_amount(total.group(1))

        return amounts

    def _parse_amount(self, amount_str: str) -> str:
        """Parse and normalize a monetary amount string."""
        # Remove dots used as thousands separator, keep comma for decimal
        cleaned = amount_str.replace(".", "").replace(",", "")
        try:
            return f"{int(cleaned):,}".replace(",", ".")
        except ValueError:
            return amount_str
