from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
import logging
import json
from core.config import settings
from core.database import get_database
from core.auth import SecurityContext, get_security_context
from schemas.interviews import (
    RoundCreateRequest,
    RoundUpdateRequest,
    CandidateStatusUpdateRequest,
    InterviewRoundResponse,
    InterviewListResponse
)

router = APIRouter(prefix="/jobs/{job_id}", tags=["interviews"])
logger = logging.getLogger(__name__)

@router.get("/interviews", response_model=InterviewListResponse)
def list_interviews(
    job_id: str,
    security: SecurityContext = Depends(get_security_context)
) -> InterviewListResponse:
    database = get_database(settings.database_dsn)
    
    # Verify job exists in the org
    job_row = database.fetchone("SELECT id FROM jobs WHERE id = %s AND org_id = %s", [job_id, security.org_id])
    if not job_row:
        raise HTTPException(status_code=404, detail="Job not found")

    rows = database.fetchall(
        """
        SELECT r.id, r.candidate_id, r.round_name, r.status, r.feedback, r.interviewer_name, r.scheduled_at, r.created_at, s.profile_json->>'name'
        FROM interview_rounds r
        JOIN candidates c ON r.candidate_id = c.id
        LEFT JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE c.org_id = %s
          AND s.profile_json->>'job_id' = %s
          AND c.status IN ('interview', 'interviewing')
          AND s.snapshot_version = (SELECT max(snapshot_version) FROM candidate_snapshots WHERE candidate_id = c.id)
        ORDER BY r.scheduled_at ASC, r.created_at ASC
        """,
        [security.org_id, job_id]
    )

    interviews = []
    for r in rows:
        interviews.append(
            InterviewRoundResponse(
                id=str(r[0]),
                candidate_id=str(r[1]),
                round_name=r[2],
                status=r[3],
                feedback=r[4],
                interviewer_name=r[5],
                scheduled_at=r[6],
                created_at=r[7],
                candidate_name=r[8] or "Unknown Candidate"
            )
        )
    return InterviewListResponse(interviews=interviews)


@router.post("/candidates/{candidate_id}/rounds", response_model=InterviewRoundResponse, status_code=status.HTTP_201_CREATED)
def create_interview_round(
    job_id: str,
    candidate_id: str,
    payload: RoundCreateRequest,
    security: SecurityContext = Depends(get_security_context)
) -> InterviewRoundResponse:
    database = get_database(settings.database_dsn)
    
    # Verify candidate belongs to the org
    cand_row = database.fetchone("SELECT id FROM candidates WHERE id = %s AND org_id = %s", [candidate_id, security.org_id])
    if not cand_row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Automatically update candidate status to 'interview'
    database.execute(
        "UPDATE candidates SET status = 'interview' WHERE id = %s AND org_id = %s",
        [candidate_id, security.org_id]
    )

    # Check if a round with the same round_name already exists for this candidate
    existing_round = database.fetchone(
        "SELECT id FROM interview_rounds WHERE candidate_id = %s AND round_name = %s AND org_id = %s",
        [candidate_id, payload.round_name, security.org_id]
    )

    if existing_round:
        round_id = existing_round[0]
        database.execute(
            """
            UPDATE interview_rounds 
            SET status = 'scheduled', interviewer_name = %s, scheduled_at = %s 
            WHERE id = %s
            """,
            [payload.interviewer_name, payload.scheduled_at, round_id]
        )
    else:
        # Insert round record
        import uuid
        round_id = str(uuid.uuid4())
        database.execute(
            """
            INSERT INTO interview_rounds (id, org_id, candidate_id, round_name, status, interviewer_name, scheduled_at)
            VALUES (%s, %s, %s, %s, 'scheduled', %s, %s)
            """,
            [round_id, security.org_id, candidate_id, payload.round_name, payload.interviewer_name, payload.scheduled_at]
        )

    # Get round details with candidate name
    r = database.fetchone(
        """
        SELECT r.id, r.candidate_id, r.round_name, r.status, r.feedback, r.interviewer_name, r.scheduled_at, r.created_at, s.profile_json->>'name'
        FROM interview_rounds r
        JOIN candidates c ON r.candidate_id = c.id
        LEFT JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE r.id = %s
          AND s.snapshot_version = (SELECT max(snapshot_version) FROM candidate_snapshots WHERE candidate_id = c.id)
        """,
        [round_id]
    )
    if not r:
        raise HTTPException(status_code=500, detail="Failed to retrieve created round")

    return InterviewRoundResponse(
        id=str(r[0]),
        candidate_id=str(r[1]),
        round_name=r[2],
        status=r[3],
        feedback=r[4],
        interviewer_name=r[5],
        scheduled_at=r[6],
        created_at=r[7],
        candidate_name=r[8] or "Unknown Candidate"
    )


@router.get("/candidates/{candidate_id}/rounds", response_model=List[InterviewRoundResponse])
def list_candidate_rounds(
    job_id: str,
    candidate_id: str,
    security: SecurityContext = Depends(get_security_context)
) -> List[InterviewRoundResponse]:
    database = get_database(settings.database_dsn)
    
    # Verify candidate belongs to the org
    cand_row = database.fetchone("SELECT id FROM candidates WHERE id = %s AND org_id = %s", [candidate_id, security.org_id])
    if not cand_row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    rows = database.fetchall(
        """
        SELECT r.id, r.candidate_id, r.round_name, r.status, r.feedback, r.interviewer_name, r.scheduled_at, r.created_at, s.profile_json->>'name'
        FROM interview_rounds r
        JOIN candidates c ON r.candidate_id = c.id
        LEFT JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE r.candidate_id = %s AND r.org_id = %s
          AND s.snapshot_version = (SELECT max(snapshot_version) FROM candidate_snapshots WHERE candidate_id = c.id)
        ORDER BY r.created_at ASC
        """,
        [candidate_id, security.org_id]
    )

    rounds = []
    for r in rows:
        rounds.append(
            InterviewRoundResponse(
                id=str(r[0]),
                candidate_id=str(r[1]),
                round_name=r[2],
                status=r[3],
                feedback=r[4],
                interviewer_name=r[5],
                scheduled_at=r[6],
                created_at=r[7],
                candidate_name=r[8] or "Unknown Candidate"
            )
        )
    return rounds


@router.patch("/candidates/{candidate_id}/rounds/{round_id}", response_model=InterviewRoundResponse)
def update_interview_round(
    job_id: str,
    candidate_id: str,
    round_id: str,
    payload: RoundUpdateRequest,
    security: SecurityContext = Depends(get_security_context)
) -> InterviewRoundResponse:
    database = get_database(settings.database_dsn)
    
    # Verify round exists and matches candidate + org
    round_row = database.fetchone(
        "SELECT id FROM interview_rounds WHERE id = %s AND candidate_id = %s AND org_id = %s",
        [round_id, candidate_id, security.org_id]
    )
    if not round_row:
        raise HTTPException(status_code=404, detail="Interview round not found")

    # Construct update statements
    updates = []
    params = []
    if payload.status is not None:
        updates.append("status = %s")
        params.append(payload.status)
    if payload.feedback is not None:
        updates.append("feedback = %s")
        params.append(payload.feedback)

    if updates:
        params.append(round_id)
        database.execute(
            f"UPDATE interview_rounds SET {', '.join(updates)} WHERE id = %s",
            params
        )

    # Fetch updated details
    r = database.fetchone(
        """
        SELECT r.id, r.candidate_id, r.round_name, r.status, r.feedback, r.interviewer_name, r.scheduled_at, r.created_at, s.profile_json->>'name'
        FROM interview_rounds r
        JOIN candidates c ON r.candidate_id = c.id
        LEFT JOIN candidate_snapshots s ON c.id = s.candidate_id
        WHERE r.id = %s
          AND s.snapshot_version = (SELECT max(snapshot_version) FROM candidate_snapshots WHERE candidate_id = c.id)
        """,
        [round_id]
    )
    return InterviewRoundResponse(
        id=str(r[0]),
        candidate_id=str(r[1]),
        round_name=r[2],
        status=r[3],
        feedback=r[4],
        interviewer_name=r[5],
        scheduled_at=r[6],
        created_at=r[7],
        candidate_name=r[8] or "Unknown Candidate"
    )


@router.post("/candidates/{candidate_id}/status")
def update_candidate_status(
    job_id: str,
    candidate_id: str,
    payload: CandidateStatusUpdateRequest,
    security: SecurityContext = Depends(get_security_context)
):
    database = get_database(settings.database_dsn)
    
    # Verify candidate belongs to org
    cand_row = database.fetchone(
        "SELECT id FROM candidates WHERE id = %s AND org_id = %s",
        [candidate_id, security.org_id]
    )
    if not cand_row:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Update candidate status
    database.execute(
        "UPDATE candidates SET status = %s WHERE id = %s",
        [payload.status, candidate_id]
    )
    return {"status": "success", "new_status": payload.status}
