from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = ROOT_DIR / "database" / "kyc.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_db_path() -> Path:
    configured = os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))
    path = Path(configured)
    if not path.is_absolute():
        path = ROOT_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kyc_cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                pan_number TEXT,
                aadhaar_number_masked TEXT,
                extracted_json TEXT NOT NULL,
                identity_json TEXT NOT NULL,
                compliance_json TEXT NOT NULL,
                risk_json TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                report_path TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reviewer_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                reviewer_decision TEXT NOT NULL,
                reviewer_notes TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES kyc_cases(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES kyc_cases(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(case_id) REFERENCES kyc_cases(id)
            )
            """
        )


def save_case(state: dict[str, Any]) -> int:
    extracted = state.get("extracted_data", {})
    aadhaar = str(extracted.get("aadhaar_number") or "")
    masked = mask_aadhaar(aadhaar)
    with connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO kyc_cases (
                customer_name,
                pan_number,
                aadhaar_number_masked,
                extracted_json,
                identity_json,
                compliance_json,
                risk_json,
                decision_json,
                report_path,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                extracted.get("name"),
                extracted.get("pan_number"),
                masked,
                json.dumps(extracted, ensure_ascii=False),
                json.dumps(state.get("identity_result", {}), ensure_ascii=False),
                json.dumps(state.get("compliance_result", {}), ensure_ascii=False),
                json.dumps(state.get("risk_result", {}), ensure_ascii=False),
                json.dumps(state.get("decision_result", {}), ensure_ascii=False),
                state.get("report_path"),
                utc_now(),
            ),
        )
        case_id = int(cur.lastrowid)
        save_agent_logs(conn, case_id, state)
        save_agent_evidence(conn, case_id, state)
        return case_id


def save_agent_logs(conn: sqlite3.Connection, case_id: int, state: dict[str, Any]) -> None:
    for item in state.get("timeline", []):
        conn.execute(
            """
            INSERT INTO agent_execution_logs (case_id, agent_name, status, summary, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (case_id, item.get("agent", ""), item.get("status", ""), item.get("summary", ""), utc_now()),
        )


def save_agent_evidence(conn: sqlite3.Connection, case_id: int, state: dict[str, Any]) -> None:
    evidence_map = {
        "Document Agent": {"pan_data": state.get("pan_data", {}), "aadhaar_data": state.get("aadhaar_data", {})},
        "Entity Resolution Agent": state.get("entity_result", {}),
        "Identity Agent": state.get("identity_result", {}),
        "Compliance Agent": state.get("compliance_result", {}),
        "Financial Agent": state.get("financial_result", {}),
        "Risk Agent": state.get("risk_result", {}),
        "Decision Agent": state.get("decision_result", {}),
    }
    for agent_name, evidence in evidence_map.items():
        conn.execute(
            """
            INSERT INTO agent_evidence (case_id, agent_name, evidence_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (case_id, agent_name, json.dumps(evidence, ensure_ascii=False), utc_now()),
        )


def save_reviewer_decision(case_id: int, decision: str, notes: str = "") -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO reviewer_decisions (
                case_id,
                reviewer_decision,
                reviewer_notes,
                created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (case_id, decision, notes, utc_now()),
        )


def list_cases(limit: int = 25) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.*, r.reviewer_decision, r.reviewer_notes, r.created_at AS reviewed_at
            FROM kyc_cases c
            LEFT JOIN (
                SELECT rd.*
                FROM reviewer_decisions rd
                INNER JOIN (
                    SELECT case_id, MAX(id) AS max_id
                    FROM reviewer_decisions
                    GROUP BY case_id
                ) latest ON latest.max_id = rd.id
            ) r ON r.case_id = c.id
            ORDER BY c.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def mask_aadhaar(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return ""
    return f"XXXX-XXXX-{digits[-4:]}"
