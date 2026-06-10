from __future__ import annotations

import re

from rapidfuzz import fuzz


def normalize_name(value: str) -> str:
    """
    Normalize names for comparison.
    Example:
        'S P Ranjith' -> 'S P RANJITH'
    """
    tokens = re.findall(r"[A-Za-z]+", value.upper())
    return " ".join(tokens)


def validate_pan(pan_number: str) -> dict:
    """
    Validate PAN format.
    """
    pan = (pan_number or "").upper().replace(" ", "")

    is_valid = bool(
        re.fullmatch(
            r"[A-Z]{5}[0-9]{4}[A-Z]",
            pan,
        )
    )

    return {
        "tool": "identity.validate_pan",
        "valid": is_valid,
        "normalized_pan": pan,
        "evidence": (
            "PAN format matched AAAAA9999A"
            if is_valid
            else "PAN format did not match AAAAA9999A"
        ),
    }


def calculate_name_similarity(
    name1: str,
    name2: str,
) -> int:
    """
    Calculate similarity score between two names.
    """

    normalized_1 = normalize_name(name1)

    normalized_2 = normalize_name(name2)

    if not normalized_1 or not normalized_2:
        return 0

    return int(
        fuzz.token_sort_ratio(
            normalized_1,
            normalized_2,
        )
    )


def compare_identity_evidence(
    pan_data: dict,
    aadhaar_data: dict,
) -> dict:
    """
    Deterministic identity comparison tool.
    """

    pan_name = str(
        pan_data.get("name", "")
    )

    aadhaar_name = str(
        aadhaar_data.get("name", "")
    )

    name_score = calculate_name_similarity(
        pan_name,
        aadhaar_name,
    )

    dob_match = bool(
        pan_data.get("dob")
        and pan_data.get("dob")
        == aadhaar_data.get("dob")
    )

    pan_check = validate_pan(
        str(
            pan_data.get(
                "pan_number",
                "",
            )
        )
    )

    #
    # Start from neutral score.
    #

    score = 80

    issues: list[str] = []

    supporting_evidence: list[str] = []

    #
    # PAN Validation
    #

    if pan_check["valid"]:

        score += 10

        supporting_evidence.append(
            "PAN number passed format validation."
        )

    else:

        score -= 35

        issues.append(
            "PAN number is missing or invalid."
        )

    #
    # Name Similarity
    #

    if name_score >= 90:

        score += 10

        supporting_evidence.append(
            f"Strong name similarity detected ({name_score})."
        )

    elif name_score >= 75:

        supporting_evidence.append(
            f"Moderate name similarity detected ({name_score})."
        )

    else:

        score -= 25

        issues.append(
            f"Low name similarity ({name_score})."
        )

    #
    # DOB Validation
    #

    if dob_match:

        score += 10

        supporting_evidence.append(
            "DOB matched across PAN and Aadhaar."
        )

    else:

        score -= 25

        issues.append(
            "DOB mismatch or missing DOB."
        )

    score = max(
        0,
        min(100, score),
    )

    return {
        "tool": "identity.compare_identity_evidence",
        "identity_match_score": score,
        "issues": issues,
        "evidence": {
            "pan_name": pan_name,
            "aadhaar_name": aadhaar_name,
            "normalized_pan_name": normalize_name(
                pan_name
            ),
            "normalized_aadhaar_name": normalize_name(
                aadhaar_name
            ),
            "name_similarity": name_score,
            "dob_match": dob_match,
            "pan_validation": pan_check,
            "supporting_evidence": supporting_evidence,
        },
    }