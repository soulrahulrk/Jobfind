from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import DEFAULT_PROFILE


def extract_pdf_text_and_links(pdf_path: Path) -> tuple[str, list[str]]:
    if not pdf_path.exists():
        return "", []

    errors: list[str] = []
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(pdf_path))
            text_parts: list[str] = []
            links: list[str] = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
                links.extend(_extract_annotation_links(page))
            return "\n".join(text_parts), sorted(set(links))
        except Exception as exc:  # pragma: no cover - best-effort fallback
            errors.append(f"{module_name}: {exc}")

    try:
        import fitz  # type: ignore

        doc = fitz.open(str(pdf_path))
        text_parts = []
        links = []
        for page in doc:
            text_parts.append(page.get_text())
            for link in page.get_links():
                uri = link.get("uri")
                if uri:
                    links.append(uri)
        return "\n".join(text_parts), sorted(set(links))
    except Exception as exc:  # pragma: no cover - best-effort fallback
        errors.append(f"fitz: {exc}")

    return "", []


def _extract_annotation_links(page: Any) -> list[str]:
    links: list[str] = []
    try:
        annotations = page.get("/Annots") or []
        for annotation in annotations:
            obj = annotation.get_object()
            action = obj.get("/A")
            if action and action.get("/URI"):
                links.append(str(action.get("/URI")))
    except Exception:
        return links
    return links


def parse_profile_from_resume(text: str, links: list[str]) -> dict[str, Any]:
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    cleaned = _normalize_text(text)

    name = _first_nonempty_line(cleaned)
    if name:
        profile["name"] = name.title()

    email = _first_match(r"[\w.\-+]+@[\w.\-]+\.\w+", cleaned)
    if email:
        profile["email"] = email

    phone = _first_match(r"(?:\+91[-\s]?)?\d{10}", cleaned)
    if phone:
        if phone.startswith("+91"):
            profile["phone"] = phone.replace(" ", "")
        else:
            profile["phone"] = f"+91-{phone[-10:]}"

    for link in links + re.findall(r"https?://[^\s)]+", cleaned):
        normalized = link.strip()
        if normalized.startswith("mailto:"):
            profile["email"] = normalized.replace("mailto:", "")
        elif "linkedin.com" in normalized:
            profile["linkedin"] = normalized
        elif "github.com" in normalized:
            profile["github"] = normalized
        elif "leetcode.com" in normalized:
            profile["leetcode"] = normalized

    if "Panipat" in cleaned:
        profile["location"] = "Panipat, India"

    skills = _extract_skills(cleaned)
    if skills:
        profile["skills"] = skills

    projects = _extract_projects(cleaned)
    if projects:
        profile["projects"] = projects

    profile["raw_text"] = cleaned
    return profile


def load_profile(pdf_path: Path) -> dict[str, Any]:
    text, links = extract_pdf_text_and_links(pdf_path)
    return parse_profile_from_resume(text, links)


def _normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        line = re.sub(r"[^A-Za-z .'-]", "", line).strip()
        if line and len(line.split()) <= 4:
            return line
    return None


def _first_match(pattern: str, text: str) -> str | None:
    match = re.search(pattern, text)
    return match.group(0) if match else None


def _extract_skills(text: str) -> list[str]:
    known = [
        "Python",
        "SQL",
        "Scikit-learn",
        "TensorFlow",
        "LangChain",
        "LangGraph",
        "NumPy",
        "Pandas",
        "Matplotlib",
        "Seaborn",
        "OpenCV",
        "Git",
        "Docker",
        "FastAPI",
        "Power BI",
        "PostgreSQL",
        "MySQL",
        "ChromaDB",
        "LLM Integration",
        "Semantic Search",
        "NLP",
        "Deep Learning",
        "Model Deployment",
        "API Development",
    ]
    lower = text.lower()
    return [skill for skill in known if skill.lower() in lower]


def _extract_projects(text: str) -> list[str]:
    candidates = [
        "AI Voyage Estimation & Decision System",
        "SHL Assessment Recommendation Engine",
        "Placement LLM - College Placement Management System",
    ]
    lower = text.lower().replace("–", "-").replace("|", " ")
    return [project for project in candidates if project.lower().replace("–", "-")[:16] in lower]
