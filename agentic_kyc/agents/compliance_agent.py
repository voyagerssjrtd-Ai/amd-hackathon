from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz


ROOT_DIR = Path(__file__).resolve().parents[1]


def run_compliance_agent(state: dict) -> dict:
    data = state.get("extracted_data", {})
    findings = []
    findings.extend(screen_file(ROOT_DIR / "data" / "watchlist.csv", "watchlist", data))
    findings.extend(screen_file(ROOT_DIR / "data" / "blacklist.csv", "blacklist", data))
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


def screen_file(path: Path, source: str, data: dict) -> list[dict]:
    if not path.exists():
        return []
    findings: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            match_score = max(
                fuzz.token_sort_ratio(data.get("name", ""), row.get("name", "")),
                exact_score(data.get("pan_number", ""), row.get("pan_number", "")),
                exact_score(mask_aadhaar(data.get("aadhaar_number", "")), row.get("aadhaar_number", "")),
            )
            dob_match = bool(data.get("dob") and data.get("dob") == row.get("dob"))
            if match_score >= 92 or (match_score >= 85 and dob_match):
                findings.append(
                    {
                        "source": source,
                        "matched_name": row.get("name", ""),
                        "match_score": round(match_score, 2),
                        "reason": row.get("reason", ""),
                        "severity": row.get("severity", "MEDIUM"),
                        "evidence": {
                            "pan_match": data.get("pan_number") == row.get("pan_number"),
                            "dob_match": dob_match,
                            "aadhaar_match": mask_aadhaar(data.get("aadhaar_number", ""))
                            == row.get("aadhaar_number", ""),
                        },
                    }
                )
    return findings


def exact_score(left: str, right: str) -> int:
    return 100 if left and right and left == right else 0


def mask_aadhaar(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else ""
