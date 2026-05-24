from pathlib import Path

from app.profile import parse_profile_from_resume


def test_parse_profile_from_resume_fixture():
    text = Path("tests/fixtures/resume_text.txt").read_text(encoding="utf-8")
    profile = parse_profile_from_resume(
        text,
        [
            "mailto:rahul.candidate@example.local",
            "https://linkedin.com/in/rahul-candidate",
            "https://github.com/example-candidate",
            "https://leetcode.com/u/example-candidate/",
        ],
    )

    assert profile["name"] == "Rahul Candidate"
    assert profile["email"] == "rahul.candidate@example.local"
    assert profile["github"] == "https://github.com/example-candidate"
    assert "Python" in profile["skills"]
    assert "FastAPI" in profile["skills"]
    assert "Placement LLM - College Placement Management System" in profile["projects"]
