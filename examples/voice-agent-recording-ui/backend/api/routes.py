"""API routes for session data management.

This module defines the REST API endpoints for retrieving session data,
including session lists, session details, and audio file streaming.
"""

import os
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
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


router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    limit: int = Query(default=50, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(default=0, ge=0, description="Number of sessions to skip"),
    status: Optional[str] = Query(default=None, description="Filter by session status"),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """List all sessions with optional filtering and pagination.

    Retrieves a paginated list of session summaries, optionally filtered
    by session status.

    Args:
        limit: Maximum number of sessions to return (1-100, default 50).
        offset: Number of sessions to skip for pagination (default 0).
        status: Optional filter for session status ('active', 'completed', 'error').
        db: Database session dependency.

    Returns:
        SessionListResponse: Paginated list of session summaries with total count.

    Raises:
        HTTPException: 400 if an invalid status value is provided.
    """
    # Build the base query
    query = select(SessionModel)
    count_query = select(func.count(SessionModel.id))

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


@router.get("/sessions/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Get detailed information about a specific session.

    Retrieves full session details including transcripts, latency
    measurements, and freeze events.

    Args:
        session_id: The unique identifier of the session.
        db: Database session dependency.

    Returns:
        SessionDetail: Complete session information with related data.

    Raises:
        HTTPException: 404 if the session is not found.
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


@router.get("/sessions/{session_id}/audio")
async def get_session_audio(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Stream the audio file for a specific session.

    Returns the audio recording for the specified session as a
    downloadable WAV file.

    Args:
        session_id: The unique identifier of the session.
        db: Database session dependency.

    Returns:
        FileResponse: The audio file as a streaming response.

    Raises:
        HTTPException: 404 if the session or audio file is not found.
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
