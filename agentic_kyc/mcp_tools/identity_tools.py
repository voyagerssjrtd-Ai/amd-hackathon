from __future__ import annotations

import re
from rapidfuzz import fuzz


def normalize_name(value: str) -> str:
    tokens = re.findall(r"[A-Za-z]+", value.upper())
    return " ".join(tokens)


def validate_pan(pan_number: str) -> dict:
    pan = (pan_number or "").upper().replace(" ", "")
    is_valid = bool(re.fullmatch(r"[A-Z]{5}[0-9]{4}[A-Z]", pan))
    return {
        "tool": "identity.validate_pan",
        "valid": is_valid,
        "normalized_pan": pan if is_valid else pan,
        "evidence": "PAN format matched AAAAA9999A" if is_valid else "PAN format did not match AAAAA9999A",
    }


def compare_identity_evidence(pan_data: dict, aadhaar_data: dict) -> dict:
    pan_name = normalize_name(str(pan_data.get("name", "")))
    aadhaar_name = normalize_name(str(aadhaar_data.get("name", "")))
    name_score = fuzz.token_sort_ratio(pan_name, aadhaar_name) if pan_name and aadhaar_name else 0
    dob_match = bool(pan_data.get("dob") and pan_data.get("dob") == aadhaar_data.get("dob"))
    pan_check = validate_pan(str(pan_data.get("pan_number", "")))

    score = 100
    issues: list[str] = []
    evidence: list[str] = []

    if not pan_check["valid"]:
        score -= 35
        issues.append("PAN number is missing or invalid")
    else:
        evidence.append("PAN number passed format validation")
    if name_score < 70:
        score -= 30
        issues.append(f"Name similarity is low: {name_score}")
    elif name_score < 88:
        score -= 12
        evidence.append(f"Name similarity is acceptable with ordering variation: {name_score}")
    else:
        evidence.append(f"Name similarity is strong: {name_score}")
    if not dob_match:
        score -= 25
        issues.append("DOB mismatch or missing DOB across documents")
    else:
        evidence.append("DOB matched across PAN and Aadhaar")

    return {
        "tool": "identity.compare_identity_evidence",
        "identity_match_score": max(0, min(100, round(score))),
        "issues": issues,
        "evidence": {
            "pan_name": pan_data.get("name", ""),
            "aadhaar_name": aadhaar_data.get("name", ""),
            "name_similarity": name_score,
            "dob_match": dob_match,
            "pan_validation": pan_check,
            "supporting_evidence": evidence,
        },
    }
