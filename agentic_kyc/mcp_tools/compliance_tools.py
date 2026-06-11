from __future__ import annotations

import csv
from pathlib import Path

from rapidfuzz import fuzz

from mcp_tools.identity_tools import normalize_name
from services.qdrant_manager import get_qdrant

MATCH_THRESHOLD = 90

def resolve_knowledge_file(knowledge_dir: Path, filename: str) -> Path | None:
    candidates = [
        knowledge_dir / "compliance_knowledge" / filename,
        knowledge_dir / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None

def screen_watchlist(
    customer_data: dict,
    knowledge_dir: Path,
) -> list[dict]:

    findings: list[dict] = []

    customer_name = normalize_name(
        customer_data.get("name", "")
    )

    if not customer_name:
        return findings

    file_path = resolve_knowledge_file(
        knowledge_dir,
        "watchlist.csv",
    )

    if not file_path:
        return findings

    with file_path.open(
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            candidate = normalize_name(
                row.get("name", "")
            )

            similarity = fuzz.token_sort_ratio(
                customer_name,
                candidate,
            )

            if similarity >= MATCH_THRESHOLD:

                findings.append(
                    {
                        "source": "watchlist",
                        "matched_name": row.get(
                            "name",
                            "",
                        ),
                        "risk": row.get(
                            "risk",
                            "MEDIUM",
                        ),
                        "reason": row.get(
                            "reason",
                            "",
                        ),
                        "similarity": similarity,
                    }
                )

    return findings

def screen_blacklist(
    customer_data: dict,
    knowledge_dir: Path,
) -> list[dict]:

    findings: list[dict] = []

    customer_name = normalize_name(
        customer_data.get("name", "")
    )

    if not customer_name:
        return findings

    file_path = resolve_knowledge_file(
        knowledge_dir,
        "blacklist.csv",
    )

    if not file_path:
        return findings

    with file_path.open(
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            candidate = normalize_name(
                row.get("name", "")
            )

            similarity = fuzz.token_sort_ratio(
                customer_name,
                candidate,
            )

            if similarity >= MATCH_THRESHOLD:

                findings.append(
                    {
                        "source": "blacklist",
                        "matched_name": row.get(
                            "name",
                            "",
                        ),
                        "risk": row.get(
                            "risk",
                            "HIGH",
                        ),
                        "reason": row.get(
                            "reason",
                            "",
                        ),
                        "similarity": similarity,
                    }
                )

    return findings

def screen_pep(
    customer_data: dict,
    knowledge_dir: Path,
) -> list[dict]:

    findings: list[dict] = []

    customer_name = normalize_name(
        customer_data.get("name", "")
    )

    if not customer_name:
        return findings

    file_path = resolve_knowledge_file(
        knowledge_dir,
        "pep.csv",
    )

    if not file_path:
        return findings

    with file_path.open(
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            candidate = normalize_name(
                row.get("name", "")
            )

            similarity = fuzz.token_sort_ratio(
                customer_name,
                candidate,
            )

            if similarity >= MATCH_THRESHOLD:

                findings.append(
                    {
                        "source": "pep",
                        "matched_name": row.get(
                            "name",
                            "",
                        ),
                        "designation": row.get(
                            "designation",
                            "",
                        ),
                        "country": row.get(
                            "country",
                            "",
                        ),
                        "risk": row.get(
                            "risk",
                            "HIGH",
                        ),
                        "reason": f"PEP match: {row.get('designation', '')}",
                        "similarity": similarity,
                    }
                )

    return findings

def retrieve_compliance_context(
    customer_data: dict,
    findings: list[dict],
    knowledge_dir: Path,
) -> list[dict]:

    try:
        qdrant = get_qdrant()

        if qdrant.count() == 0:
            qdrant.load_compliance_knowledge(
                knowledge_dir,
            )

    except Exception as exc:
        return [
            {
                "score": 0,
                "source": "QDRANT_UNAVAILABLE",
                "content": f"Compliance RAG unavailable: {exc}",
                "risk": "UNKNOWN",
            }
        ]

    query_parts = []

    for finding in findings:
        query_parts.append(finding.get("source", ""))
        query_parts.append(finding.get("reason", ""))

    for key in ["name", "pan_number", "dob"]:
        value = str(customer_data.get(key, "") or "").strip()

        if value:
            query_parts.append(value)

    fraud_terms = [
        "sample only",
        "test data",
        "not a valid id",
        "tampered",
        "fake",
        "forged",
    ]

    document_text = str(
        customer_data.get(
            "document_text",
            "",
        )
    ).lower()

    for term in fraud_terms:
        if term in document_text:
            query_parts.append(
                f"fraud indicator {term}"
            )

    if not query_parts:
            query_parts.append(
                "customer due diligence aml policy rbi guideline"
            )

    query = " ".join(query_parts)

    try:
        results = qdrant.search(
            query=query,
            limit=5,
        )

        return [
            item
            for item in results
            if item.get("score", 0) >= 0.70
        ]

    except Exception as exc:
        return [
            {
                "score": 0,
                "source": "QDRANT_SEARCH_ERROR",
                "content": f"Compliance RAG search failed: {exc}",
                "risk": "UNKNOWN",
            }
        ]

def run_compliance_screening(
    customer_data: dict,
    knowledge_dir: Path,
) -> dict:

    watchlist = screen_watchlist(
        customer_data,
        knowledge_dir,
    )

    blacklist = screen_blacklist(
        customer_data,
        knowledge_dir,
    )

    pep = screen_pep(
        customer_data,
        knowledge_dir,
    )

    findings = (
        watchlist
        + blacklist
        + pep
    )

    rag_context = retrieve_compliance_context(
        customer_data=customer_data,
        findings=findings,
        knowledge_dir=knowledge_dir,
    )
    
    return {
        "status": (
            "REVIEW"
            if findings
            else "CLEAR"
        ),
        "findings": findings,
        "rag_context": rag_context,
        "tool_evidence": {
            "watchlist": watchlist,
            "blacklist": blacklist,
            "pep": pep,
            "rag_context": rag_context,
        },
    }


