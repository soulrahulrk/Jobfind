from __future__ import annotations

import base64
import json
import os
import re
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from .config import CONFIG_DIR, DATA_DIR, ROLE_TERMS
from .database import get_profile, list_sources, upsert_job
from .ranking import parse_salary_text, score_job

USER_AGENT = "RahulLocalJobFinder/1.0"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def run_scan(conn, include_network: bool = True) -> dict[str, Any]:
    profile = get_profile(conn)
    sources = [source for source in list_sources(conn) if source["enabled"]]
    jobs: list[dict[str, Any]] = []
    errors: list[str] = []

    if include_network:
        for fetcher in (fetch_remotive_jobs, fetch_himalayas_jobs, fetch_jobicy_jobs, fetch_adzuna_jobs, fetch_gmail_alert_jobs):
            try:
                jobs.extend(fetcher())
            except Exception as exc:
                errors.append(f"{fetcher.__name__}: {exc}")

    stored = 0
    for job in _dedupe_jobs(jobs):
        salary_min, salary_max, salary_text = parse_salary_text(job.get("salary_text") or job.get("raw_text"))
        job.setdefault("salary_min", salary_min)
        job.setdefault("salary_max", salary_max)
        job.setdefault("salary_text", salary_text)
        score, reasons = score_job(job, profile)
        upsert_job(conn, job, score, reasons)
        stored += 1

    return {
        "stored": stored,
        "errors": errors,
        "sources": [source["name"] for source in sources],
    }


def fetch_remotive_jobs() -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    for term in ROLE_TERMS[:6]:
        query = urllib.parse.urlencode({"category": "software-dev", "search": term, "limit": 50})
        payload = _fetch_json(f"https://remotive.com/api/remote-jobs?{query}")
        for item in payload.get("jobs", []):
            all_jobs.append(
                {
                    "source": "Remotive",
                    "source_job_id": str(item.get("id") or ""),
                    "title": item.get("title") or "Untitled remote role",
                    "company": item.get("company_name"),
                    "location": item.get("candidate_required_location") or "Remote",
                    "remote": True,
                    "salary_text": item.get("salary"),
                    "apply_url": item.get("url"),
                    "posted_at": item.get("publication_date"),
                    "raw_text": _strip_html(item.get("description") or ""),
                    "raw_json": item,
                }
            )
    return all_jobs


def fetch_adzuna_jobs() -> list[dict[str, Any]]:
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        return []

    all_jobs: list[dict[str, Any]] = []
    for term in ROLE_TERMS:
        query = urllib.parse.urlencode(
            {
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 50,
                "what": term,
                "where": "India",
                "content-type": "application/json",
                "sort_by": "date",
            }
        )
        payload = _fetch_json(f"https://api.adzuna.com/v1/api/jobs/in/search/1?{query}")
        for item in payload.get("results", []):
            location = item.get("location", {}).get("display_name")
            company = item.get("company", {}).get("display_name")
            salary_text = _format_salary(item.get("salary_min"), item.get("salary_max"))
            all_jobs.append(
                {
                    "source": "Adzuna",
                    "source_job_id": str(item.get("id") or ""),
                    "title": item.get("title") or "Untitled role",
                    "company": company,
                    "location": location,
                    "remote": "remote" in f"{location} {item.get('description')}".lower(),
                    "salary_min": _safe_int(item.get("salary_min")),
                    "salary_max": _safe_int(item.get("salary_max")),
                    "salary_text": salary_text,
                    "apply_url": item.get("redirect_url"),
                    "posted_at": item.get("created"),
                    "raw_text": item.get("description") or "",
                    "raw_json": item,
                }
            )
    return all_jobs


def fetch_himalayas_jobs() -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    for term in ROLE_TERMS[:7]:
        query = urllib.parse.urlencode({"q": term, "sort": "recent", "page": 1})
        payload = _fetch_json(f"https://himalayas.app/jobs/api/search?{query}")
        for item in payload.get("jobs", []):
            restrictions = item.get("locationRestrictions") or []
            location = "Worldwide" if not restrictions else ", ".join(restrictions)
            currency = item.get("currency")
            salary_text = _format_currency_salary(currency, item.get("minSalary"), item.get("maxSalary"), "annual")
            salary_min, salary_max = _monthly_inr_salary(currency, item.get("minSalary"), item.get("maxSalary"), "annual")
            all_jobs.append(
                {
                    "source": "Himalayas",
                    "source_job_id": str(item.get("guid") or item.get("applicationLink") or ""),
                    "title": item.get("title") or "Untitled remote role",
                    "company": item.get("companyName"),
                    "location": location,
                    "remote": True,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "salary_text": salary_text,
                    "experience_min": 0 if str(item.get("seniority") or "").lower() in {"entry-level", "junior"} else None,
                    "experience_max": 2 if str(item.get("seniority") or "").lower() in {"entry-level", "junior"} else None,
                    "apply_url": item.get("applicationLink"),
                    "posted_at": item.get("pubDate"),
                    "raw_text": _strip_html(" ".join(str(item.get(key) or "") for key in ("excerpt", "description", "seniority", "employmentType"))),
                    "raw_json": item,
                }
            )
    return all_jobs


def fetch_jobicy_jobs() -> list[dict[str, Any]]:
    all_jobs: list[dict[str, Any]] = []
    for term in ROLE_TERMS[:7]:
        query = urllib.parse.urlencode({"count": 50, "tag": term})
        payload = _fetch_json(f"https://jobicy.com/api/v2/remote-jobs?{query}")
        for item in payload.get("jobs", []):
            currency = item.get("salaryCurrency")
            period = item.get("salaryPeriod")
            salary_text = _format_currency_salary(currency, item.get("salaryMin"), item.get("salaryMax"), period)
            salary_min, salary_max = _monthly_inr_salary(currency, item.get("salaryMin"), item.get("salaryMax"), period)
            all_jobs.append(
                {
                    "source": "Jobicy",
                    "source_job_id": str(item.get("id") or item.get("url") or ""),
                    "title": item.get("jobTitle") or "Untitled remote role",
                    "company": item.get("companyName"),
                    "location": item.get("jobGeo") or "Remote",
                    "remote": True,
                    "salary_min": salary_min,
                    "salary_max": salary_max,
                    "salary_text": salary_text,
                    "apply_url": item.get("url"),
                    "posted_at": item.get("pubDate"),
                    "raw_text": _strip_html(" ".join(str(item.get(key) or "") for key in ("jobExcerpt", "jobDescription", "jobLevel", "jobType", "jobIndustry"))),
                    "raw_json": item,
                }
            )
    return all_jobs


def fetch_gmail_alert_jobs() -> list[dict[str, Any]]:
    credentials_path = CONFIG_DIR / "gmail_credentials.json"
    token_path = DATA_DIR / "gmail_token.json"
    if not credentials_path.exists():
        return []

    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Google API libraries are not installed") from exc

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    service = build("gmail", "v1", credentials=creds)
    query = 'newer_than:30d (job OR jobs OR hiring OR internship OR "machine learning" OR python)'
    response = service.users().messages().list(userId="me", q=query, maxResults=50).execute()
    jobs = []
    for message in response.get("messages", []):
        detail = service.users().messages().get(userId="me", id=message["id"], format="full").execute()
        jobs.extend(_jobs_from_gmail_message(detail))
    return jobs


def _jobs_from_gmail_message(message: dict[str, Any]) -> list[dict[str, Any]]:
    headers = {item["name"].lower(): item["value"] for item in message.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "Job alert")
    sender = headers.get("from", "Gmail")
    date = headers.get("date")
    posted_at = None
    if date:
        try:
            posted_at = parsedate_to_datetime(date).isoformat()
        except (TypeError, ValueError):
            posted_at = None
    body = _payload_text(message.get("payload", {}))
    links = _extract_links(body)
    useful_links = [link for link in links if _looks_like_job_link(link)]
    jobs = []
    for index, link in enumerate(useful_links[:8]):
        title = _clean_subject(subject)
        jobs.append(
            {
                "source": "Gmail Job Alerts",
                "source_job_id": f"{message.get('id')}-{index}",
                "title": title,
                "company": _sender_company(sender),
                "location": "India / Remote",
                "remote": "remote" in body.lower(),
                "apply_url": link,
                "posted_at": posted_at,
                "raw_text": body[:4000],
                "raw_json": {"message_id": message.get("id"), "subject": subject, "from": sender},
            }
        )
    return jobs


def _fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _dedupe_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result = []
    for job in jobs:
        key = "|".join(str(job.get(field) or "").lower() for field in ("source", "source_job_id", "apply_url", "title"))
        if key in seen:
            continue
        seen.add(key)
        if job.get("title"):
            result.append(job)
    return result


def _payload_text(payload: dict[str, Any]) -> str:
    parts = payload.get("parts") or []
    if not parts and payload.get("body"):
        parts = [payload]
    chunks = []
    for part in parts:
        mime = part.get("mimeType", "")
        if part.get("parts"):
            chunks.append(_payload_text(part))
            continue
        data = part.get("body", {}).get("data")
        if data and (mime.startswith("text/") or mime in ("", "text")):
            decoded = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="ignore")
            chunks.append(_strip_html(decoded))
    return "\n".join(chunks)


def _extract_links(text: str) -> list[str]:
    return sorted(set(re.findall(r"https?://[^\s<>\"]+", text)))


def _looks_like_job_link(link: str) -> bool:
    lower = urllib.parse.unquote(link).lower()
    domains = ("linkedin", "naukri", "internshala", "indeed", "wellfound", "cutshort", "unstop", "foundit")
    return any(domain in lower for domain in domains) and any(token in lower for token in ("job", "jobs", "intern", "view"))


def _clean_subject(subject: str) -> str:
    subject = re.sub(r"(?i)\b(job alert|jobs? for you|new jobs?|hiring)\b", "", subject)
    subject = re.sub(r"\s+", " ", subject).strip(" -:|")
    return subject or "Job alert match"


def _sender_company(sender: str) -> str:
    match = re.search(r"@([\w.\-]+)", sender)
    if not match:
        return sender
    domain = match.group(1).split(".")[0]
    return domain.title()


def _strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _format_salary(min_value: Any, max_value: Any) -> str | None:
    if min_value is None and max_value is None:
        return None
    if min_value and max_value:
        return f"INR {int(float(min_value))} - {int(float(max_value))}"
    return f"INR {int(float(min_value or max_value))}"


def _format_currency_salary(currency: Any, min_value: Any, max_value: Any, period: Any) -> str | None:
    if min_value is None and max_value is None:
        return None
    code = str(currency or "").upper() or "SALARY"
    cadence = str(period or "").lower()
    if min_value and max_value:
        return f"{code} {int(float(min_value))} - {int(float(max_value))} {cadence}".strip()
    return f"{code} {int(float(min_value or max_value))} {cadence}".strip()


def _monthly_inr_salary(currency: Any, min_value: Any, max_value: Any, period: Any) -> tuple[int | None, int | None]:
    if str(currency or "").upper() != "INR":
        return None, None
    divisor = 12 if "year" in str(period or "").lower() or "annual" in str(period or "").lower() else 1
    values = []
    for value in (min_value, max_value):
        safe = _safe_int(value)
        values.append(int(safe / divisor) if safe else None)
    return values[0], values[1]
