from fastapi.testclient import TestClient
from pathlib import Path
from uuid import uuid4

from app.database import connect, init_db, upsert_job, upsert_profile
from app.main import create_app
from app.ranking import score_job


def test_api_lists_jobs_and_updates_status():
    db_path = Path("tests") / f"test_jobfinder_{uuid4().hex}.sqlite3"
    with connect(db_path) as conn:
        init_db(conn)
        upsert_profile(conn, {"name": "Rahul Candidate", "salary_floor_inr_monthly": 10000})
        job = {
            "source": "Fixture",
            "source_job_id": "1",
            "title": "Python AI Fresher",
            "company": "Acme",
            "location": "Remote India",
            "remote": True,
            "salary_min": 20000,
            "apply_url": "https://example.com/apply",
            "raw_text": "Python Machine Learning FastAPI fresher",
        }
        score, reasons = score_job(job, {})
        upsert_job(conn, job, score, reasons)

    app = create_app(db_path)
    with TestClient(app) as client:
        response = client.get("/api/jobs?min_score=0")
        assert response.status_code == 200
        jobs = response.json()
        assert len(jobs) == 1
        assert jobs[0]["title"] == "Python AI Fresher"

        status_response = client.put(
            f"/api/jobs/{jobs[0]['id']}/status",
            json={"status": "applied", "notes": "Applied through direct link"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "applied"

        filtered = client.get("/api/jobs?status=applied&min_score=0").json()
        assert len(filtered) == 1
        assert filtered[0]["notes"] == "Applied through direct link"
