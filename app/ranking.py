from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

POSITIVE_TERMS: dict[str, int] = {
    "ai": 5,
    "artificial intelligence": 12,
    "machine learning": 14,
    "ml": 6,
    "data science": 12,
    "data scientist": 12,
    "python": 13,
    "fastapi": 10,
    "langchain": 10,
    "langgraph": 10,
    "llm": 12,
    "generative ai": 12,
    "nlp": 9,
    "computer vision": 10,
    "opencv": 8,
    "sql": 6,
    "power bi": 6,
    "pandas": 6,
    "tensorflow": 8,
    "scikit": 7,
    "chroma": 6,
    "api": 4,
}

FRESHER_TERMS = {
    "fresher",
    "freshers",
    "entry level",
    "entry-level",
    "graduate",
    "trainee",
    "intern",
    "internship",
    "0-1 years",
    "0 to 1",
    "0-2 years",
}

SENIOR_TERMS = {
    "senior",
    "lead",
    "principal",
    "staff",
    "architect",
    "manager",
    "director",
    "5+ years",
    "4+ years",
    "3+ years",
}

JS_ONLY_TERMS = {
    "react",
    "frontend",
    "front end",
    "node.js",
    "nodejs",
    "javascript",
    "typescript",
}


def score_job(job: dict[str, Any], profile: dict[str, Any] | None = None) -> tuple[int, list[str]]:
    text = _job_text(job)
    title = str(job.get("title") or "").lower()
    score = 35
    reasons: list[str] = []

    matched_terms = []
    for term, points in POSITIVE_TERMS.items():
        if term in text:
            score += points
            matched_terms.append(term)
    if matched_terms:
        reasons.append("Skill match: " + ", ".join(sorted(set(matched_terms))[:6]))

    if any(term in text for term in FRESHER_TERMS):
        score += 16
        reasons.append("Freshers/entry-level wording found")

    if job.get("remote"):
        score += 8
        reasons.append("Remote-friendly")

    location = str(job.get("location") or "").lower()
    if any(term in location for term in ("india", "remote", "panipat", "delhi", "gurugram", "noida", "bangalore", "hyderabad")):
        score += 6
        reasons.append("Location matches India/remote preference")

    salary_min = _to_int(job.get("salary_min"))
    if salary_min and salary_min >= 10_000:
        score += 6
        reasons.append("Salary floor is satisfied")
    elif "unpaid" in text:
        score -= 25
        reasons.append("Unpaid role")

    max_exp = _extract_max_experience(job, text)
    if max_exp is not None:
        if max_exp <= 2:
            score += 10
            reasons.append("Experience requirement is 0-2 years")
        elif max_exp >= 3:
            score -= 22
            reasons.append("Experience requirement is above fresher level")

    if any(term in title for term in SENIOR_TERMS) or any(term in text for term in SENIOR_TERMS):
        score -= 28
        reasons.append("Senior/lead wording found")

    if _looks_javascript_only(text):
        score -= 10
        reasons.append("Mostly JavaScript/frontend focused")

    if not job.get("apply_url"):
        score -= 35
        reasons.append("Missing direct apply link")

    stale_days = _days_since(job.get("posted_at"))
    if stale_days is not None:
        if stale_days <= 14:
            score += 6
            reasons.append("Recently posted")
        elif stale_days > 60:
            score -= 10
            reasons.append("Older than 60 days")

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("Basic match from title and source")
    return score, reasons


def parse_salary_text(text: str | None) -> tuple[int | None, int | None, str | None]:
    if not text:
        return None, None, None
    raw = " ".join(str(text).split())
    lower = raw.lower()
    if "unpaid" in lower:
        return 0, 0, raw

    numbers = [float(value.replace(",", "")) for value in re.findall(r"\d+(?:,\d+)*(?:\.\d+)?", raw)]
    if not numbers:
        return None, None, raw

    multiplier = 1
    monthly_divisor = 1
    if "lpa" in lower or "lakh" in lower or "lakhs" in lower:
        multiplier = 100_000
        monthly_divisor = 12
    elif "k" in lower and not "week" in lower:
        multiplier = 1_000
    elif "year" in lower or "annual" in lower or "annum" in lower:
        monthly_divisor = 12

    converted = [int((num * multiplier) / monthly_divisor) for num in numbers[:2]]
    if len(converted) == 1:
        return converted[0], converted[0], raw
    return min(converted), max(converted), raw


def _job_text(job: dict[str, Any]) -> str:
    values = [
        job.get("title"),
        job.get("company"),
        job.get("location"),
        job.get("salary_text"),
        job.get("raw_text"),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _extract_max_experience(job: dict[str, Any], text: str) -> float | None:
    for key in ("experience_max", "experience_min"):
        value = _to_int(job.get(key))
        if value is not None:
            return float(value)
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:\+|to|-)?\s*(?:\d+(?:\.\d+)?)?\s*(?:years?|yrs?)", text)
    if not matches:
        return None
    return max(float(match) for match in matches)


def _looks_javascript_only(text: str) -> bool:
    has_js = any(term in text for term in JS_ONLY_TERMS)
    has_python_or_ai = any(term in text for term in ("python", "machine learning", "ai", "data science", "ml"))
    return has_js and not has_python_or_ai


def _days_since(value: Any) -> int | None:
    if not value:
        return None
    raw = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).days
