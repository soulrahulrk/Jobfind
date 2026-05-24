# Local Job Finder for Rahul

Local-first job search dashboard for fresher AI/ML, Data Science, Python, FastAPI, LLM, NLP, CV, and Data Analyst roles.

The app stores data in SQLite inside this project. It does not store job-site passwords. Gmail support uses Google OAuth with readonly access when configured.

Your resume PDF, extracted profile, Gmail token, scanned jobs, and application notes are local-only data and are not committed to GitHub.

## Run

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Sources

Enabled by default:

- Himalayas remote jobs API
- Jobicy remote jobs API
- Remotive remote jobs API
- Saved search links for LinkedIn, Naukri, Internshala, Wellfound, and Cutshort

Optional:

Adzuna:

```powershell
$env:ADZUNA_APP_ID="your_app_id"
$env:ADZUNA_APP_KEY="your_app_key"
```

Gmail readonly alerts:

1. Create a Google OAuth desktop client.
2. Save the JSON file as `config/gmail_credentials.json`.
3. Start the app and run a scan. The first Gmail scan opens the OAuth consent flow.

The token is stored at `data/gmail_token.json`. Delete it any time to revoke local access.

## Daily Scan

The helper script creates a Windows Task Scheduler job for 09:00 Asia/Kolkata:

```powershell
.\scripts\register_daily_scan.ps1
```

## Tests

```powershell
pytest
```
