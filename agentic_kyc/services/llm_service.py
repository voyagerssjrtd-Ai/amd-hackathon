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
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

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
