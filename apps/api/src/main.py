from fastapi import FastAPI

from api.routes import candidates, health, jobs, rankings
from core.config import settings

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(rankings.router)
