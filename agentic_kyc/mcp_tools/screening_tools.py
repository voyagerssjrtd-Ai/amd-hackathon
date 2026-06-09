from __future__ import annotations

import csv
from pathlib import Path
from rapidfuzz import fuzz


def search_watchlists(customer: dict, data_dir: str | Path) -> dict:
    data_path = Path(data_dir)
    findings: list[dict] = []
    findings.extend(_screen_file(data_path / "watchlist.csv", "watchlist", customer))
    findings.extend(_screen_file(data_path / "blacklist.csv", "blacklist", customer))
    return {
        "tool": "screening.search_watchlists",
        "status": "REVIEW" if findings else "CLEAR",
        "findings": findings,
        "evidence": f"Screened {customer.get('name', '')} against watchlist.csv and blacklist.csv",
    }


def _screen_file(path: Path, source: str, customer: dict) -> list[dict]:
    if not path.exists():
        return []
    findings: list[dict] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name_score = fuzz.token_sort_ratio(customer.get("name", ""), row.get("name", ""))
            pan_match = bool(customer.get("pan_number") and customer.get("pan_number") == row.get("pan_number"))
            aadhaar_match = _mask_aadhaar(customer.get("aadhaar_number", "")) == row.get("aadhaar_number", "")
            dob_match = bool(customer.get("dob") and customer.get("dob") == row.get("dob"))
            if pan_match or aadhaar_match or name_score >= 92 or (name_score >= 86 and dob_match):
                findings.append(
                    {
                        "source": source,
                        "matched_name": row.get("name", ""),
                        "match_score": 100 if pan_match or aadhaar_match else round(name_score, 2),
                        "reason": row.get("reason", ""),
                        "severity": row.get("severity", "MEDIUM"),
                        "evidence": {
                            "name_similarity": round(name_score, 2),
                            "pan_match": pan_match,
                            "dob_match": dob_match,
                            "aadhaar_match": aadhaar_match,
                        },
                    }
                )
    return findings


def _mask_aadhaar(value: str) -> str:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return f"XXXX-XXXX-{digits[-4:]}" if len(digits) >= 4 else ""
