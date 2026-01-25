"""API routes for session data management.

This module defines the REST API endpoints for retrieving session data,
including session lists, session details, and audio file streaming.
"""

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.schemas import (
    SessionDetail,
    SessionListResponse,
    SessionSummary,
)
from backend.db import Session as SessionModel
from backend.db import SessionStatus, get_db
from backend.db.models import utc_now


router = APIRouter(prefix="/api", tags=["sessions"])


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List all sessions",
    response_description="Paginated list of session summaries",
)
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(default=0, ge=0, description="Number of sessions to skip"),
    status: Optional[str] = Query(
        default=None,
        description="Filter by session status",
        enum=["active", "completed", "error"],
    ),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """List all sessions with optional filtering and pagination.

    Returns a paginated list of session summaries ordered by creation date
    (newest first). Use the `status` parameter to filter by session state.

    **Pagination:**
    - Use `limit` and `offset` for pagination
    - Maximum 100 sessions per request
    - Response includes `total` count for calculating pages

    **Example:**
    ```
    GET /api/sessions?limit=10&offset=0&status=completed
    ```
    """
    # Build the base query - exclude soft-deleted sessions
    query = select(SessionModel).where(SessionModel.deleted_at.is_(None))
    count_query = select(func.count(SessionModel.id)).where(SessionModel.deleted_at.is_(None))

    # Apply status filter if provided
    if status is not None:
        try:
            status_enum = SessionStatus(status)
            query = query.where(SessionModel.status == status_enum)
            count_query = count_query.where(SessionModel.status == status_enum)
        except ValueError:
            valid_statuses = [s.value for s in SessionStatus]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values are: {valid_statuses}",
            )

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(SessionModel.created_at.desc()).offset(offset).limit(limit)

    # Execute query
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Convert to response models
    session_summaries = [SessionSummary.model_validate(session) for session in sessions]

    return SessionListResponse(sessions=session_summaries, total=total)


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetail,
    summary="Get session details",
    response_description="Complete session information with transcripts, latencies, and freeze events",
    responses={
        404: {"description": "Session not found"},
    },
)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Get detailed information about a specific session.

    Returns full session details including:
    - **Transcripts**: All user and assistant messages with timestamps
    - **Turn latencies**: Response time measurements for each conversation turn
    - **Freeze events**: Detected periods where the bot stopped responding

    Use this data to analyze conversation quality and identify performance issues.
    """
    # Query session with eager loading of relationships
    query = (
        select(SessionModel)
        .options(
            selectinload(SessionModel.transcripts),
            selectinload(SessionModel.turn_latencies),
            selectinload(SessionModel.freeze_events),
        )
        .where(SessionModel.id == session_id)
    )

    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session with id '{session_id}' not found",
        )

    return SessionDetail.model_validate(session)


@router.get(
    "/sessions/{session_id}/audio",
    summary="Download session audio",
    response_description="WAV audio file of the session recording",
    responses={
        200: {
            "content": {"audio/wav": {}},
            "description": "Audio file stream",
        },
        404: {"description": "Session or audio file not found"},
    },
)
async def get_session_audio(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download the audio recording for a specific session.

    Returns the session's audio recording as a WAV file. The audio is recorded
    in stereo format:
    - **Left channel**: User audio
    - **Right channel**: Bot audio

    **Audio specifications:**
    - Format: WAV (PCM)
    - Sample rate: 16kHz
    - Channels: 2 (stereo)
    - Bit depth: 16-bit
    """
    # Query session to get audio file path
    query = select(SessionModel).where(SessionModel.id == session_id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session with id '{session_id}' not found",
        )

    if session.audio_file_path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No audio file available for session '{session_id}'",
        )

    # Verify the audio file exists on disk
    if not os.path.isfile(session.audio_file_path):
        raise HTTPException(
            status_code=404,
            detail=f"Audio file not found on disk for session '{session_id}'",
        )

    return FileResponse(
        path=session.audio_file_path,
        media_type="audio/wav",
        filename=f"session_{session_id}.wav",
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
    response_description="Session successfully deleted",
    responses={
        204: {"description": "Session successfully deleted"},
        404: {"description": "Session not found"},
    },
)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Soft delete a session by setting its deleted_at timestamp.

    The session is not physically removed from the database but marked as
    deleted. Deleted sessions will not appear in list queries.

    Returns 204 No Content on successful deletion.
    """
    # Query session to verify it exists and is not already deleted
    query = select(SessionModel).where(
        SessionModel.id == session_id,
        SessionModel.deleted_at.is_(None),
    )

    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session with id '{session_id}' not found",
        )

    # Set deleted_at timestamp
    session.deleted_at = utc_now()
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
