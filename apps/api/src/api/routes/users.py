import hashlib
import hmac
import os
import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.config import settings
from core.database import get_database

router = APIRouter(prefix="/users", tags=["users"])


# ---------------------------------------------------------------------------
# Lightweight in-memory rate limiting for the auth endpoints (no extra deps).
# Single-instance scope — fine for the current deployment; use a shared store
# (e.g. Redis) if the api is ever scaled to multiple instances.
# ---------------------------------------------------------------------------

_RATE_LIMIT = 10          # max attempts...
_RATE_WINDOW = 60.0       # ...per this many seconds, per IP + bucket
_attempts: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Behind the Vercel/Render proxies the real client is in X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request, bucket: str) -> None:
    key = f"{bucket}:{_client_ip(request)}"
    now = time.monotonic()
    dq = _attempts[key]
    while dq and now - dq[0] > _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a minute and try again.")
    dq.append(now)


# ---------------------------------------------------------------------------
# Password hashing (stdlib pbkdf2 — no extra dependency)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored or "$" not in stored:
        return False
    salt_hex, hash_hex = stored.split("$", 1)
    try:
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 200_000)
    except ValueError:
        return False
    return hmac.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    id: str
    org_id: str
    full_name: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=AuthResponse, status_code=201)
def register_user(payload: RegisterRequest, request: Request) -> AuthResponse:
    _rate_limit(request, "register")
    database = get_database(settings.database_dsn)

    email = payload.email.strip().lower()
    if not email or not payload.password:
        raise HTTPException(status_code=400, detail="Email and password are required")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    existing = database.fetchone("SELECT id FROM users WHERE email = %s", [email])
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    full_name = (payload.full_name or "").strip() or email.split("@")[0]
    org_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    # Each new account gets its own organization → all data is naturally isolated per user.
    database.execute(
        "INSERT INTO organizations (id, name) VALUES (%s, %s)",
        [org_id, f"{full_name}'s Workspace"],
    )
    database.execute(
        "INSERT INTO users (id, org_id, email, full_name, status, password_hash) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        [user_id, org_id, email, full_name, "active", hash_password(payload.password)],
    )
    return AuthResponse(id=user_id, org_id=org_id, full_name=full_name)


@router.post("/login", response_model=AuthResponse)
def login_user(payload: LoginRequest, request: Request) -> AuthResponse:
    _rate_limit(request, "login")
    database = get_database(settings.database_dsn)
    email = payload.email.strip().lower()

    row = database.fetchone(
        "SELECT id, org_id, full_name, password_hash FROM users WHERE email = %s",
        [email],
    )
    if not row or not verify_password(payload.password, row[3] or ""):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return AuthResponse(id=str(row[0]), org_id=str(row[1]), full_name=row[2] or email)
