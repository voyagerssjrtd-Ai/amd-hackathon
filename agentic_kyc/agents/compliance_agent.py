from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz

from services.llm_service import LLMService


ROOT_DIR = Path(__file__).resolve().parents[1]


def run_compliance_agent(state: dict) -> dict:
    data = state.get("extracted_data", {})
    findings = []
    findings.extend(screen_file(ROOT_DIR / "data" / "watchlist.csv", "watchlist", data))
    findings.extend(screen_file(ROOT_DIR / "data" / "blacklist.csv", "blacklist", data))
    payload = {"customer": data, "candidate_findings": findings}
    try:
        result = enforce_compliance_gates(LLMService().assess_compliance(payload), findings)
    except Exception:
        result = {"status": "REVIEW" if findings else "CLEAR", "findings": findings}
    timeline = state.get("timeline", [])
    timeline.append(
        {
            "agent": "Compliance Agent",
            "status": "completed",
            "summary": "Screened customer against sample watchlist and blacklist datasets.",
        }
    )
    return {**state, "compliance_result": result, "timeline": timeline}


def enforce_compliance_gates(result: dict, findings: list[dict]) -> dict:
    if findings:
        return {"status": "REVIEW", "findings": findings}
    return {"status": "CLEAR", "findings": []}


def screen_file(path: Path, source: str, data: dict) -> list[dict]:
    if not path.exists():
        return []
    findings: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            # Calculate match scores with proper normalization
            name_score = fuzz.token_sort_ratio(data.get("name", ""), row.get("name", ""))
            pan_score = exact_score(data.get("pan_number", ""), row.get("pan_number", ""))
            aadhaar_score = exact_score(
                mask_aadhaar(data.get("aadhaar_number", "")), 
                row.get("aadhaar_number", "")
            )
            match_score = max(name_score, pan_score, aadhaar_score)
            dob_match = bool(data.get("dob") and data.get("dob") == row.get("dob"))
            
            # Matching logic: exact PAN or Aadhaar match is enough, OR high name similarity + DOB match
            pan_match = pan_score == 100
            aadhaar_match = aadhaar_score == 100
            name_dob_match = name_score >= 92 and dob_match
            
            if pan_match or aadhaar_match or name_dob_match or (match_score >= 85 and dob_match):
                findings.append(
                    {
                        "source": source,
                        "matched_name": row.get("name", ""),
                        "match_score": round(match_score, 2),
                        "reason": row.get("reason", ""),
                        "severity": row.get("severity", "MEDIUM"),
                        "evidence": {
                            "pan_match": pan_match,
                            "dob_match": dob_match,
                            "aadhaar_match": aadhaar_match,
                            "name_match_score": round(name_score, 2),
                        },
                    }
                )
    return findings


def exact_score(left: str, right: str) -> int:
    # Normalize both strings for comparison: uppercase and remove spaces
    left_normalized = "".join(ch for ch in str(left).upper() if ch.isalnum())
    right_normalized = "".join(ch for ch in str(right).upper() if ch.isalnum())
    return 100 if left_normalized and right_normalized and left_normalized == right_normalized else 0


def mask_aadhaar(value: str) -> str:
    # Normalize Aadhaar: extract digits and format consistently
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else ""


def normalize_pan(value: str) -> str:
    # Normalize PAN: uppercase and remove spaces
    return "".join(ch for ch in str(value).upper() if ch.isalnum())
