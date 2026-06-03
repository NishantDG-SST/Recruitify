from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


@router.get("/")
def root() -> dict:
    return {"service": "recruitment-platform", "version": "0.1.0"}
