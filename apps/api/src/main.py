from fastapi import FastAPI

from api.routes import candidates, health, jobs, rankings, users, interviews
from core.config import settings

app = FastAPI(title=settings.api_title, version=settings.api_version)

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(candidates.router)
app.include_router(rankings.router)
app.include_router(users.router)
app.include_router(interviews.router)


@app.on_event("startup")
def startup_db_seed():
    from core.database import get_database
    database = get_database(settings.database_dsn)
    if database.is_configured:
        # Seed org 1
        database.execute(
            "INSERT INTO organizations (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            ["11111111-1111-1111-1111-111111111111", "Demo Org 1"]
        )
        # Seed user 1
        database.execute(
            "INSERT INTO users (id, org_id, email, full_name, status) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            ["22222222-2222-2222-2222-222222222222", "11111111-1111-1111-1111-111111111111", "demo1@example.com", "Demo User 1", "active"]
        )
        # Seed org 2
        database.execute(
            "INSERT INTO organizations (id, name) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
            ["00000000-0000-0000-0000-000000000001", "Demo Org 2"]
        )
        # Seed user 2
        database.execute(
            "INSERT INTO users (id, org_id, email, full_name, status) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
            ["00000000-0000-0000-0000-000000000002", "00000000-0000-0000-0000-000000000001", "demo2@example.com", "Demo User 2", "active"]
        )


@app.on_event("startup")
def validate_embedding_provider():
    import logging
    import os
    from services.llm.client import LLMClient, LLMConfig
    logger = logging.getLogger("startup")
    
    gemini_key = os.getenv("GEMINI_API_KEY", settings.gemini_api_key)
    if not gemini_key or gemini_key.startswith("gsk_"):
        logger.warning("Embedding Provider Status: UNAVAILABLE (GEMINI_API_KEY is not set or invalid; falling back to zero-vectors)")
        return
        
    client = LLMClient(LLMConfig(
        api_key=settings.openai_api_key,
        gemini_api_key=gemini_key,
        base_url=settings.openai_base_url,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
    ))
    
    try:
        client.embed(["test startup"])
        logger.info("Embedding Provider Status: ACTIVE (Google Gemini text-embedding-004 is working)")
    except Exception as e:
        logger.error(f"Embedding Provider Status: UNAVAILABLE (Embedding verification failed: {e})")


