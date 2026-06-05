from fastapi import Header
from typing import Optional

DEMO_ORG_ID = "11111111-1111-1111-1111-111111111111"
DEMO_USER_ID = "22222222-2222-2222-2222-222222222222"

class SecurityContext:
    def __init__(self, org_id: str, user_id: str):
        self.org_id = org_id
        self.user_id = user_id

def get_security_context(
    x_org_id: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
) -> SecurityContext:
    import uuid
    from fastapi import HTTPException
    
    if x_org_id:
        try:
            uuid.UUID(x_org_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Org-Id format (must be a valid UUID)")
            
    if x_user_id:
        try:
            uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-User-Id format (must be a valid UUID)")

    org_id = x_org_id or DEMO_ORG_ID
    user_id = x_user_id or DEMO_USER_ID
    
    # Ensure demo organization and user exist if we fall back to them
    if org_id == DEMO_ORG_ID or user_id == DEMO_USER_ID:
        from core.database import get_database
        from core.config import settings
        database = get_database(settings.database_dsn)
        
        org_exists = database.fetchone("SELECT id FROM organizations WHERE id = %s", [DEMO_ORG_ID])
        if not org_exists:
            database.execute(
                "INSERT INTO organizations (id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                [DEMO_ORG_ID, "Demo Org"]
            )
        
        user_exists = database.fetchone("SELECT id FROM users WHERE id = %s", [DEMO_USER_ID])
        if not user_exists:
            database.execute(
                "INSERT INTO users (id, org_id, email, full_name, status) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                [DEMO_USER_ID, DEMO_ORG_ID, "demo@example.com", "Demo User", "active"]
            )
            
    return SecurityContext(org_id=org_id, user_id=user_id)
