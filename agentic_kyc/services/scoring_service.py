from __future__ import annotations

from rapidfuzz import fuzz


REQUIRED_FIELDS = ["name", "dob", "pan_number", "aadhaar_number", "address"]


def identity_score(data: dict[str, str], pan_text: str, aadhaar_text: str) -> dict:
    issues: list[str] = []
    extracted_name = data.get("name", "")
    pan_name = field_from_text(pan_text, ["name", "customer name"])
    aadhaar_name = field_from_text(aadhaar_text, ["name", "customer name"])
    pan_dob = field_from_text(pan_text, ["date of birth", "dob", "birth date"])
    aadhaar_dob = field_from_text(aadhaar_text, ["date of birth", "dob", "birth date"])
    aadhaar_address = field_from_text(aadhaar_text, ["address"])

    name_similarity = max(
        fuzz.token_sort_ratio(extracted_name, pan_name),
        fuzz.token_sort_ratio(pan_name, aadhaar_name),
        fuzz.token_sort_ratio(extracted_name, aadhaar_name),
    )
    if pan_name and aadhaar_name and fuzz.token_sort_ratio(pan_name, aadhaar_name) < 85:
        issues.append(f"Name mismatch: PAN='{pan_name}' Aadhaar='{aadhaar_name}'")
    if pan_dob and aadhaar_dob and normalize_simple_date(pan_dob) != normalize_simple_date(aadhaar_dob):
        issues.append(f"DOB mismatch: PAN='{pan_dob}' Aadhaar='{aadhaar_dob}'")
    if data.get("address") and aadhaar_address:
        address_similarity = fuzz.token_sort_ratio(data["address"], aadhaar_address)
    else:
        address_similarity = 100 if data.get("address") else 65
    if address_similarity < 70:
        issues.append("Address similarity below review threshold")

    missing = [field for field in REQUIRED_FIELDS if not data.get(field)]
    for field in missing:
        issues.append(f"Missing required field: {field}")

    score = 100
    score -= max(0, 100 - name_similarity) * 0.35
    score -= 20 if any("DOB mismatch" in issue for issue in issues) else 0
    score -= 15 if address_similarity < 70 else 0
    score -= len(missing) * 8
    return {
        "identity_match_score": max(0, min(100, round(score))),
        "issues": issues,
        "evidence": {
            "pan_name": pan_name,
            "aadhaar_name": aadhaar_name,
            "pan_dob": pan_dob,
            "aadhaar_dob": aadhaar_dob,
            "name_similarity": round(name_similarity, 2),
            "address_similarity": round(address_similarity, 2),
        },
    }


def calculate_risk(
    extracted_data: dict[str, str],
    identity_result: dict,
    compliance_result: dict,
) -> dict:
    score = 10
    reasons = ["PAN extracted successfully" if extracted_data.get("pan_number") else "PAN number missing"]
    reasons.append(
        "Aadhaar extracted successfully" if extracted_data.get("aadhaar_number") else "Aadhaar number missing"
    )

    missing = [field for field in REQUIRED_FIELDS if not extracted_data.get(field)]
    if missing:
        score += len(missing) * 12
        reasons.append(f"Missing fields detected: {', '.join(missing)}")

    identity_score_value = identity_result.get("identity_match_score", 0)
    if identity_score_value < 85:
        delta = min(30, round((85 - identity_score_value) * 0.7))
        score += delta
        reasons.extend(identity_result.get("issues", []))
    else:
        reasons.append("Identity fields are consistent across documents")

    findings = compliance_result.get("findings", [])
    watchlist_hits = [item for item in findings if item.get("source") == "watchlist"]
    blacklist_hits = [item for item in findings if item.get("source") == "blacklist"]
    if watchlist_hits:
        score += 35
        reasons.append("Watchlist hit detected")
    if blacklist_hits:
        score += 55
        reasons.append("Blacklist hit detected")
    if not findings:
        reasons.append("No watchlist or blacklist match found")

    score = max(0, min(100, score))
    if score >= 75:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    else:
        level = "LOW"
    return {"risk_score": score, "risk_level": level, "reasons": dedupe(reasons)}


def field_from_text(text: str, labels: list[str]) -> str:
    for line in text.splitlines():
        lower = line.lower()
        for label in labels:
            if lower.startswith(label.lower()):
                return line.split(":", 1)[-1].strip() if ":" in line else line.split("-", 1)[-1].strip()
    return ""


def normalize_simple_date(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result
