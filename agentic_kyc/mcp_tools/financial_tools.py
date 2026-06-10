from __future__ import annotations

import re
from pathlib import Path

from services.pdf_service import extract_text_from_document


def extract_amount(patterns: list[str], text: str) -> float | None:
    """
    Extract the first valid amount matching any of the supplied patterns.
    """
    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except (TypeError, ValueError):
                continue

    return None

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
            "evidence": [
                "No bank statement or payslip uploaded."
            ],
        }

    text = extract_text_from_document(Path(path))
    text_lower = text.lower()
    tampering_reasons: list[str] = []
    #
    # Fraud indicators.
    #
    fraud_markers = [
        "sample only",
        "test data",
        "not a valid id",
        "specimen",
        "training data",
    ]

    for marker in fraud_markers:

        if marker in text_lower:

            tampering_reasons.append(
                f"Document contains fraud marker: '{marker}'."
            )

    if not re.search(
        r"bank statement|salary|payslip|credited|debit|credit|balance|emi|loan|account statement",
        text,
        re.I,
    ):
        return {
            "tool": "financial.analyze_document",
            "status": "NOT_FINANCIAL",
            "monthly_income": None,
            "average_balance": None,
            "debt_ratio": None,
            "employment_stability": "UNKNOWN",
            "financial_risk": "UNKNOWN",
            "evidence": [
                "Uploaded file did not contain financial indicators."
            ],
        }

    #
    # PAYSLIP ANALYSIS
    #

    net_pay = extract_amount(
        [
            r"Net\s*Pay\s*([0-9,]+\.\d{2})",
            r"Net\s*Salary\s*([0-9,]+\.\d{2})",
        ],
        text,
    )

    total_earnings = extract_amount(
        [
            r"Total\s*Earnings.*?([0-9,]+\.\d{2})",
        ],
        text,
    )
    corrected_amount = extract_amount(
        [
            r"Correct\s*Figure\s*of\s*₹?\s*([0-9,]+)",
            r"Corrected\s*Amount\s*₹?\s*([0-9,]+)",
        ],
        text,
    )

    annual_income = extract_amount(
        [
            r"Annual\s*Income.*?([0-9,]+\.\d{2})",
        ],
        text,
    )

    #
    # Prefer NET PAY as monthly income.
    #

    monthly_income = None

    if net_pay:
        monthly_income = round(net_pay, 2)

    elif total_earnings:
        monthly_income = round(total_earnings, 2)

    elif annual_income:
        monthly_income = round(annual_income / 12, 2)
    
    #
    # Conflicting salary detection.
    #
    if (
        net_pay
        and corrected_amount
        and abs(net_pay - corrected_amount) > 500
    ):

        tampering_reasons.append(
            f"Conflicting salary values detected "
            f"(Net Pay={net_pay}, "
            f"Correct Figure={corrected_amount})."
        )
    #
    # Average balance only for bank statements.
    #

    balance_matches = re.findall(
        r"(?:closing\s*balance|available\s*balance|balance)\D+([0-9,]+\.\d{2})",
        text,
        re.I,
    )

    balances = []

    for value in balance_matches:
        try:
            balances.append(
                float(value.replace(",", ""))
            )
        except (TypeError, ValueError):
            continue

    average_balance = (
        round(sum(balances) / len(balances), 2)
        if balances
        else None
    )

    #
    # Debt indicators.
    #

    debt_terms = len(
        re.findall(
            r"loan|emi|credit\s*card|overdraft|debt",
            text,
            re.I,
        )
    )

    debt_ratio = (
        round(min(debt_terms * 0.10, 0.50), 2)
        if monthly_income
        else None
    )
    #
    # Tampering override.
    #
    if tampering_reasons:

        return {
            "tool": "financial.analyze_document",

            "status": "TAMPERED",

            "monthly_income": monthly_income,

            "average_balance": average_balance,

            "debt_ratio": debt_ratio,

            "employment_stability": "UNKNOWN",

            "financial_risk": "HIGH",

            "tampering_detected": True,

            "evidence": tampering_reasons,
        }
    #
    # Financial Risk Assessment
    #
    if monthly_income is None:

        stability = "UNKNOWN"
        financial_risk = "UNKNOWN"

    elif monthly_income >= 75000:

        stability = "HIGH"

        financial_risk = (
            "LOW"
            if debt_terms <= 1
            else "MEDIUM"
        )

    elif monthly_income >= 30000:

        stability = "MEDIUM"

        financial_risk = (
            "LOW"
            if debt_terms == 0
            else "MEDIUM"
        )

    else:

        stability = "LOW"

        financial_risk = "HIGH"

    return {
        "tool": "financial.analyze_document",
        "status": "ANALYZED",
        "monthly_income": monthly_income,
        "average_balance": average_balance,
        "debt_ratio": debt_ratio,
        "employment_stability": stability,
        "financial_risk": financial_risk,
        "evidence": [
            f"Net Pay detected: {net_pay}"
            if net_pay
            else "Net Pay not detected.",

            f"Total Earnings detected: {total_earnings}"
            if total_earnings
            else "Total Earnings not detected.",

            f"Debt indicators found: {debt_terms}",
        ],
    }
