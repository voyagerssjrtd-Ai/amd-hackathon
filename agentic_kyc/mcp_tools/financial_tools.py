from __future__ import annotations

import re
from pathlib import Path

from services.pdf_service import extract_text_from_document


def analyze_financial_document(path: str | None) -> dict:
    if not path:
        return {
            "tool": "financial.analyze_document",
            "status": "NOT_PROVIDED",
            "monthly_income": None,
            "average_balance": None,
            "debt_ratio": None,
            "employment_stability": "UNKNOWN",
            "financial_risk": "UNKNOWN",
            "evidence": ["No bank statement or payslip uploaded."],
        }

    text = extract_text_from_document(Path(path))
    amounts = [float(item.replace(",", "")) for item in re.findall(r"(?:INR|Rs\.?|₹)?\s*([0-9][0-9,]{3,}(?:\.\d+)?)", text)]
    income_candidates = [amount for amount in amounts if amount >= 10000]
    monthly_income = max(income_candidates) if income_candidates else None
    average_balance = round(sum(amounts) / len(amounts), 2) if amounts else None
    debt_terms = len(re.findall(r"loan|emi|credit\s*card|overdraft|debt", text, re.I))
    debt_ratio = min(0.9, round(debt_terms * 0.12, 2)) if monthly_income else None

    if monthly_income and monthly_income >= 75000 and debt_terms <= 1:
        stability, financial_risk = "HIGH", "LOW"
    elif monthly_income and monthly_income >= 30000:
        stability, financial_risk = "MEDIUM", "MEDIUM"
    else:
        stability, financial_risk = "LOW" if monthly_income else "UNKNOWN", "HIGH" if monthly_income else "UNKNOWN"

    return {
        "tool": "financial.analyze_document",
        "status": "ANALYZED",
        "monthly_income": monthly_income,
        "average_balance": average_balance,
        "debt_ratio": debt_ratio,
        "employment_stability": stability,
        "financial_risk": financial_risk,
        "evidence": [
            f"Detected {len(amounts)} monetary values.",
            f"Detected {debt_terms} debt-related terms.",
        ],
    }
