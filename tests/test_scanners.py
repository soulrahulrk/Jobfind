from app.scanners import _jobs_from_gmail_message


def test_gmail_message_extracts_job_links():
    message = {
        "id": "abc123",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Python fresher jobs for you"},
                {"name": "From", "value": "LinkedIn <jobs@linkedin.com>"},
                {"name": "Date", "value": "Tue, 20 May 2026 10:00:00 +0000"},
            ],
            "body": {
                "data": "UGxlYXNlIGFwcGx5IGF0IGh0dHBzOi8vd3d3LmxpbmtlZGluLmNvbS9qb2JzL3ZpZXcvcHl0aG9uLWZyZXNoZXI=",
            },
            "mimeType": "text/plain",
        },
    }

    jobs = _jobs_from_gmail_message(message)

    assert len(jobs) == 1
    assert jobs[0]["source"] == "Gmail Job Alerts"
    assert "linkedin.com/jobs/view" in jobs[0]["apply_url"]
