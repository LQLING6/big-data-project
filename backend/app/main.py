from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routers import admin, auth, competitions, me

app = FastAPI(title="赛知 CampusComp AI", version="0.1.0", description="本地教学基础工程；默认仅合成数据、规则推荐和站内提醒。")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["*"], allow_headers=["*"], allow_credentials=False)

for router in [auth.router, competitions.router, me.router, admin.router]:
    app.include_router(router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health():
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ok", "demo_mode": settings.demo_mode, "ai_provider": "rules", "email_provider": "disabled"}


# A built frontend can be served by the same process. API routes stay ahead of this mount.
frontend_dist = Path(__file__).resolve().parents[2] / "frontend-dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
