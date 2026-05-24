from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import traceback
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import DATA_DIR, DB_PATH, RESUME_PATH
from .database import connect, get_profile, init_db, list_jobs, list_sources, update_status, upsert_profile
from .profile import load_profile
from .scanners import run_scan

STATIC_DIR = Path(__file__).resolve().parent / "static"


class StatusUpdate(BaseModel):
    status: str
    notes: str | None = None


class SourceCreate(BaseModel):
    name: str
    url: str
    kind: str = "saved_search"
    enabled: bool = True


def create_app(db_path: Path | str = DB_PATH) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with connect(app.state.db_path) as conn:
            init_db(conn)
            if not get_profile(conn):
                upsert_profile(conn, load_profile(RESUME_PATH))
        yield

    app = FastAPI(title="Rahul Local Job Finder", version="1.0.0", lifespan=lifespan)
    app.state.db_path = Path(db_path)

    @app.middleware("http")
    async def log_api_errors(request, call_next):
        try:
            response = await call_next(request)
            if request.url.path.startswith("/api") and response.status_code >= 500:
                _append_http_log(f"{request.method} {request.url.path} -> {response.status_code}")
            return response
        except Exception:
            _append_http_log(f"{request.method} {request.url.path}\n{traceback.format_exc()}")
            raise

    def get_conn():
        conn = connect(app.state.db_path)
        try:
            yield conn
        finally:
            conn.close()

    @app.get("/")
    def dashboard():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/profile")
    def api_profile(conn=Depends(get_conn)):
        return get_profile(conn)

    @app.post("/api/profile/reload")
    def api_profile_reload(conn=Depends(get_conn)):
        profile = load_profile(RESUME_PATH)
        upsert_profile(conn, profile)
        return profile

    @app.get("/api/sources")
    def api_sources(conn=Depends(get_conn)):
        return list_sources(conn)

    @app.post("/api/sources")
    def api_create_source(source: SourceCreate, conn=Depends(get_conn)):
        from .database import upsert_source

        upsert_source(conn, source.model_dump())
        return list_sources(conn)

    @app.get("/api/jobs")
    def api_jobs(
        q: str | None = None,
        source: str | None = None,
        status: str | None = None,
        remote: bool = False,
        min_score: int | None = Query(default=None, ge=0, le=100),
        salary_floor: bool = False,
        conn=Depends(get_conn),
    ):
        return list_jobs(
            conn,
            {
                "q": q,
                "source": source,
                "status": status,
                "remote": remote,
                "min_score": min_score,
                "salary_floor": salary_floor,
            },
        )

    @app.post("/api/scan")
    def api_scan(conn=Depends(get_conn)) -> dict[str, Any]:
        return run_scan(conn, include_network=True)

    @app.put("/api/jobs/{job_id}/status")
    def api_status(job_id: int, payload: StatusUpdate, conn=Depends(get_conn)):
        try:
            return update_status(conn, job_id, payload.status, payload.notes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()


def _append_http_log(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with (DATA_DIR / "http_errors.log").open("a", encoding="utf-8") as handle:
        handle.write(message)
        handle.write("\n---\n")
