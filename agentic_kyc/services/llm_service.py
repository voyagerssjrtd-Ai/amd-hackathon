from __future__ import annotations

import json
import os
import re
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


class LLMService:
    def __init__(self) -> None:
        self.base_url = os.getenv("BASE_URL", "http://localhost:8000/v1")
        self.model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
        self.api_key = os.getenv("OPENAI_API_KEY", "EMPTY")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=20.0, max_retries=0)

    def extract_json(self, pan_text: str, aadhaar_text: str) -> dict[str, Any]:
        prompt = f"""
You are a KYC document extraction agent. Convert the provided PAN and Aadhaar text into strict JSON.
Return only JSON with these keys: name, dob, pan_number, aadhaar_number, address.
Use ISO date format YYYY-MM-DD when possible. If a field is unavailable, use an empty string.

PAN_TEXT:
{pan_text}

AADHAAR_TEXT:
{aadhaar_text}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=600,
            )
            content = response.choices[0].message.content or "{}"
            return normalize_extracted_json(parse_json_object(content))
        except Exception:
            return rule_based_extract(pan_text, aadhaar_text)

    def extract_document_json(self, document_type: str, text: str) -> dict[str, Any]:
        prompt = f"""
You are a specialist KYC extraction agent for one Indian identity document.
Document type: {document_type}

Extract only fields that are visible in this document. Do not infer missing values from another document.
Return strict JSON with keys: name, dob, pan_number, aadhaar_number, address, extraction_confidence, evidence.
`evidence` must list the exact visible clues used. If a field is not visible, use an empty string.

DOCUMENT_TEXT:
{text}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only. Never invent missing KYC fields."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=700,
            )
            content = response.choices[0].message.content or "{}"
            return normalize_document_json(parse_json_object(content))
        except Exception:
            return normalize_document_json(rule_based_extract_single(text))

    def verify_identity(self, pan_data: dict[str, Any], aadhaar_data: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are an Identity Verification Agent. Compare PAN and Aadhaar extraction results.
Return strict JSON:
{{
  "identity_match_score": 0-100,
  "issues": [],
  "evidence": {{}}
}}

Rules:
- Missing PAN number is a major issue.
- Missing PAN name or PAN DOB means the identity match cannot be considered strong.
- Do not give a high score using Aadhaar-only evidence.
- Name and DOB must be consistent across both documents when both are present.

PAN_DATA:
{json.dumps(pan_data, ensure_ascii=False)}

AADHAAR_DATA:
{json.dumps(aadhaar_data, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=700,
            )
            parsed = parse_json_object(response.choices[0].message.content or "{}")
            return normalize_identity_json(parsed)
        except Exception:
            raise

    def score_risk(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are a KYC Risk Scoring Agent. Produce an explainable risk score.
Return strict JSON:
{{
  "risk_score": 0-100,
  "risk_level": "LOW|MEDIUM|HIGH",
  "reasons": []
}}

Hard rules:
- Missing PAN number must be at least MEDIUM risk and score >= 55.
- Missing both PAN name and PAN number must score >= 70.
- Any blacklist hit must be HIGH risk and score >= 90.
- Any watchlist hit must be at least MEDIUM risk and score >= 65.
- Approve-quality low risk requires both documents to provide core identity evidence.

CASE:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=800,
            )
            parsed = parse_json_object(response.choices[0].message.content or "{}")
            return normalize_risk_json(parsed)
        except Exception:
            raise

    def assess_compliance(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are a Compliance Screening Agent. Review simulated watchlist and blacklist evidence.
Return strict JSON:
{{
  "status": "CLEAR|REVIEW",
  "findings": []
}}

Rules:
- If there are any candidate findings, status must be REVIEW.
- Preserve source, matched_name, match_score, reason, severity, and evidence for each real finding.
- If no findings exist, status is CLEAR and findings is [].

SCREENING_PAYLOAD:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=900,
            )
            parsed = parse_json_object(response.choices[0].message.content or "{}")
            status = str(parsed.get("status", "REVIEW")).upper()
            return {
                "status": "CLEAR" if status == "CLEAR" and not payload.get("candidate_findings") else "REVIEW"
                if payload.get("candidate_findings")
                else "CLEAR",
                "findings": parsed.get("findings", payload.get("candidate_findings", [])),
            }
        except Exception:
            raise

    def make_decision(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = f"""
You are a senior KYC Decision Agent. Recommend APPROVE, REVIEW, or ESCALATE.
Return strict JSON:
{{
  "recommendation": "APPROVE|REVIEW|ESCALATE",
  "explanation": "",
  "evidence": {{}}
}}

Hard rules:
- Missing PAN number cannot be APPROVE.
- Missing PAN extraction evidence cannot be APPROVE.
- HIGH risk should ESCALATE unless the only cause is a recoverable extraction failure, then REVIEW.
- Compliance blacklist hit must ESCALATE.
- Low risk with complete PAN and Aadhaar evidence can APPROVE.

CASE:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=800,
            )
            parsed = parse_json_object(response.choices[0].message.content or "{}")
            return normalize_decision_json(parsed)
        except Exception:
            raise

    def extract_text_from_image(self, image_b64: str, mime_type: str = "image/png") -> str:
        prompt = (
            "Read this Indian KYC document image. Extract all visible text exactly enough for downstream "
            "KYC parsing. Include name, date of birth, PAN number, Aadhaar number, and address if present."
        )
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                            },
                        ],
                    }
                ],
                temperature=0,
                max_tokens=900,
            )
            return response.choices[0].message.content or ""
        except Exception:
            return ""


def parse_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def normalize_extracted_json(data: dict[str, Any]) -> dict[str, str]:
    keys = ["name", "dob", "pan_number", "aadhaar_number", "address"]
    normalized = {key: str(data.get(key, "") or "").strip() for key in keys}
    normalized["pan_number"] = normalized["pan_number"].upper().replace(" ", "")
    normalized["aadhaar_number"] = format_aadhaar(normalized["aadhaar_number"])
    normalized["dob"] = normalize_date(normalized["dob"])
    return normalized


def normalize_document_json(data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_extracted_json(data)
    confidence = data.get("extraction_confidence", 0)
    try:
        confidence = int(float(confidence))
    except (TypeError, ValueError):
        confidence = 0
    evidence = data.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    normalized["extraction_confidence"] = max(0, min(100, confidence))
    normalized["evidence"] = [str(item) for item in evidence if str(item).strip()]
    return normalized


def normalize_identity_json(data: dict[str, Any]) -> dict[str, Any]:
    try:
        score = int(float(data.get("identity_match_score", 0)))
    except (TypeError, ValueError):
        score = 0
    issues = data.get("issues", [])
    if isinstance(issues, str):
        issues = [issues]
    evidence = data.get("evidence", {})
    return {
        "identity_match_score": max(0, min(100, score)),
        "issues": [str(item) for item in issues if str(item).strip()],
        "evidence": evidence if isinstance(evidence, dict) else {"notes": str(evidence)},
    }


def normalize_risk_json(data: dict[str, Any]) -> dict[str, Any]:
    try:
        score = int(float(data.get("risk_score", 100)))
    except (TypeError, ValueError):
        score = 100
    score = max(0, min(100, score))
    level = str(data.get("risk_level", "")).upper()
    if level not in {"LOW", "MEDIUM", "HIGH"}:
        level = "HIGH" if score >= 75 else "MEDIUM" if score >= 40 else "LOW"
    reasons = data.get("reasons", [])
    if isinstance(reasons, str):
        reasons = [reasons]
    return {"risk_score": score, "risk_level": level, "reasons": [str(item) for item in reasons if str(item).strip()]}


def normalize_decision_json(data: dict[str, Any]) -> dict[str, Any]:
    recommendation = str(data.get("recommendation", "REVIEW")).upper()
    if recommendation not in {"APPROVE", "REVIEW", "ESCALATE"}:
        recommendation = "REVIEW"
    evidence = data.get("evidence", {})
    return {
        "recommendation": recommendation,
        "explanation": str(data.get("explanation", "") or "Decision generated by KYC Decision Agent."),
        "evidence": evidence if isinstance(evidence, dict) else {"notes": str(evidence)},
    }


def rule_based_extract(pan_text: str, aadhaar_text: str) -> dict[str, str]:
    combined = f"{pan_text}\n{aadhaar_text}"
    name = first_match(
        combined,
        [
            r"(?im)^\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .'-]{2,})\s*$",
            r"(?im)^\s*customer\s*name\s*[:\-]\s*([A-Za-z][A-Za-z .'-]{2,})\s*$",
        ],
    )
    dob = first_match(
        combined,
        [
            r"(?im)(?:date of birth|dob|birth date)\s*[:\-]\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
            r"(?im)(?:date of birth|dob|birth date)\s*[:\-]\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})",
        ],
    )
    pan = first_match(combined, [r"\b([A-Z]{5}[0-9]{4}[A-Z])\b"])
    aadhaar = first_match(combined, [r"\b([0-9]{4}\s?[0-9]{4}\s?[0-9]{4})\b"])
    address = first_match(
        aadhaar_text,
        [
            r"(?im)^\s*address\s*[:\-]\s*(.+)$",
            r"(?ims)address\s*[:\-]\s*(.+?)(?:\n\s*(?:dob|aadhaar|$))",
        ],
    )
    return normalize_extracted_json(
        {
            "name": name,
            "dob": dob,
            "pan_number": pan,
            "aadhaar_number": aadhaar,
            "address": address,
        }
    )


def rule_based_extract_single(document_text: str) -> dict[str, Any]:
    extracted = rule_based_extract(document_text, document_text)
    present = sum(1 for key in ["name", "dob", "pan_number", "aadhaar_number", "address"] if extracted.get(key))
    extracted["extraction_confidence"] = min(100, present * 20)
    extracted["evidence"] = [line.strip() for line in document_text.splitlines()[:8] if line.strip()]
    return extracted


def first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ""


def normalize_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = re.split(r"[-/]", value)
    if len(parts) != 3:
        return value
    if len(parts[0]) == 4:
        yyyy, mm, dd = parts
    else:
        dd, mm, yyyy = parts
        if len(yyyy) == 2:
            yyyy = f"19{yyyy}" if int(yyyy) > 30 else f"20{yyyy}"
    return f"{int(yyyy):04d}-{int(mm):02d}-{int(dd):02d}"


def format_aadhaar(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 12:
        return f"{digits[0:4]} {digits[4:8]} {digits[8:12]}"
    return value.strip()
