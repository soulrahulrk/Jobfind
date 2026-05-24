from app.ranking import parse_salary_text, score_job


def test_score_boosts_fresher_ai_python_roles():
    job = {
        "title": "Machine Learning Engineer Fresher",
        "company": "Example AI",
        "location": "Remote India",
        "remote": True,
        "salary_min": 25000,
        "apply_url": "https://example.com/jobs/ml-fresher",
        "raw_text": "Python, FastAPI, LangChain, TensorFlow, SQL. 0-1 years experience.",
    }

    score, reasons = score_job(job, {})

    assert score >= 80
    assert any("Skill match" in reason for reason in reasons)
    assert any("Freshers" in reason for reason in reasons)


def test_score_penalizes_senior_frontend_without_python():
    job = {
        "title": "Senior React Lead",
        "company": "Example",
        "location": "Bengaluru",
        "remote": False,
        "apply_url": "https://example.com/jobs/senior-react",
        "raw_text": "React, JavaScript, TypeScript. 5+ years experience.",
    }

    score, reasons = score_job(job, {})

    assert score < 45
    assert any("Senior" in reason for reason in reasons)


def test_parse_lpa_salary_as_monthly_inr():
    salary_min, salary_max, raw = parse_salary_text("INR 3 - 6 LPA")

    assert salary_min == 25000
    assert salary_max == 50000
    assert raw == "INR 3 - 6 LPA"
