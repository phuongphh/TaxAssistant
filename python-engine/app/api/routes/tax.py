"""
REST API routes for Tax Engine.
Used for admin tools, testing, and direct API access.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.tax_engine import TaxEngine
from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext

router = APIRouter(prefix="/api/tax", tags=["tax"])

# Singleton engine instance
_engine = TaxEngine()


class MessageRequest(BaseModel):
    message: str
    customer_type: str = "unknown"
    session_context: dict | None = None


class CalculateRequest(BaseModel):
    category: str  # vat, cit, pit, license
    customer_type: str = "sme"
    revenue: float | None = None
    income: float | None = None
    industry_code: str | None = None
    extra: dict = {}


class TaxInfoRequest(BaseModel):
    category: str
    customer_type: str = "sme"


@router.post("/message")
async def process_message(req: MessageRequest):
    """Process a tax-related message (REST alternative to gRPC)."""
    result = await _engine.process_message(
        message=req.message,
        customer_type=req.customer_type,
        session_context=req.session_context,
    )
    return result


@router.post("/calculate")
async def calculate_tax(req: CalculateRequest):
    """Direct tax calculation endpoint."""
    try:
        category = TaxCategory(req.category)
    except ValueError:
        return {"error": f"Unknown tax category: {req.category}"}

    ct = CustomerType(req.customer_type) if req.customer_type in [e.value for e in CustomerType] else CustomerType.UNKNOWN

    rule = _engine.tax_rules.get(category)
    if not rule:
        return {"error": f"No rule found for category: {req.category}"}

    context = TaxContext(
        customer_type=ct,
        revenue=req.revenue,
        income=req.income,
        industry_code=req.industry_code,
        extra=req.extra,
    )

    result = rule.calculate(context)
    return {
        "category": result.category.value,
        "amount": result.amount,
        "rate": result.rate,
        "explanation": result.explanation,
        "legal_basis": result.legal_basis,
        "warnings": result.warnings,
    }


@router.get("/info/{category}")
async def tax_info(category: str, customer_type: str = "sme"):
    """Get general information about a tax type."""
    try:
        cat = TaxCategory(category)
    except ValueError:
        return {"error": f"Unknown tax category: {category}"}

    ct = CustomerType(customer_type) if customer_type in [e.value for e in CustomerType] else CustomerType.UNKNOWN

    rule = _engine.tax_rules.get(cat)
    if not rule:
        return {"error": f"No rule found for category: {category}"}

    return {
        "category": category,
        "customer_type": customer_type,
        "info": rule.get_info(ct),
    }


@router.get("/categories")
async def list_categories():
    """List all supported tax categories."""
    return {
        "categories": [
            {"code": cat.value, "name": name}
            for cat, name in [
                (TaxCategory.VAT, "Thuế GTGT"),
                (TaxCategory.CIT, "Thuế TNDN"),
                (TaxCategory.PIT, "Thuế TNCN"),
                (TaxCategory.LICENSE, "Thuế Môn bài"),
            ]
        ]
    }
