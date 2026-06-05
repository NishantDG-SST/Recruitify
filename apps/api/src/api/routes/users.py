from fastapi import APIRouter
from pydantic import BaseModel
from core.config import settings
from core.database import get_database

router = APIRouter(prefix="/users", tags=["users"])

class UserSyncRequest(BaseModel):
    email: str
    full_name: str

class UserSyncResponse(BaseModel):
    id: str
    org_id: str

@router.post("/sync", response_model=UserSyncResponse)
def sync_user(payload: UserSyncRequest) -> UserSyncResponse:
    database = get_database(settings.database_dsn)
    
    # 1. Check if user already exists
    user_row = database.fetchone(
        "SELECT id, org_id FROM users WHERE email = %s",
        [payload.email]
    )
    if user_row:
        return UserSyncResponse(id=str(user_row[0]), org_id=str(user_row[1]))
        
    # 2. If not, create organization and user dynamically
    import uuid
    new_org_id = str(uuid.uuid4())
    new_user_id = str(uuid.uuid4())
    
    database.execute(
        "INSERT INTO organizations (id, name) VALUES (%s, %s)",
        [new_org_id, f"{payload.full_name}'s Org"]
    )
    
    database.execute(
        "INSERT INTO users (id, org_id, email, full_name, status) VALUES (%s, %s, %s, %s, %s)",
        [new_user_id, new_org_id, payload.email, payload.full_name, "active"]
    )
    
    return UserSyncResponse(id=new_user_id, org_id=new_org_id)
