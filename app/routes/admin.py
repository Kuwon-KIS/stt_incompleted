"""Admin API routes for database management."""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.database import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])

# Initialize database manager
db = DatabaseManager()


class DBStatusResponse(BaseModel):
    """Database status response model."""
    db_file: str
    jobs: int
    results: int
    dates: int
    initialized: bool


class DateStatItem(BaseModel):
    """Date statistics item."""
    date: str
    total_files: int
    processed_files: int
    failed_files: int
    status: str
    last_processed: Optional[str] = None


class DateStatsResponse(BaseModel):
    """Date statistics response."""
    dates: List[DateStatItem]
    total_dates: int
    total_files: int
    total_success: int
    total_failed: int


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str


@router.post("/db/init", response_model=MessageResponse)
async def init_database():
    """Initialize database schema."""
    try:
        db.init_db()
        logger.info("Database initialized via admin API")
        return {"message": "Database initialized successfully"}
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/db/reset", response_model=MessageResponse)
async def reset_database():
    """Reset database - drop all tables and reinitialize."""
    try:
        db.reset_db()
        logger.warning("Database reset via admin API")
        return {"message": "Database reset successfully"}
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/db/status", response_model=DBStatusResponse)
async def get_database_status():
    """Get database status."""
    try:
        status_info = db.get_db_status()
        return DBStatusResponse(**status_info)
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/date-stats", response_model=DateStatsResponse)
async def get_date_statistics(
    start_date: Optional[str] = Query(None, description="Start date (YYYYMMDD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYYMMDD)")
):
    """Get date-wise statistics for dashboard display (unified API endpoint).
    
    This endpoint provides date statistics in array format, suitable for dashboard tables.
    Internally uses the same data source as /calendar/status/{year}/{month}.
    
    Optional date range filtering for dashboard filtering needs.
    
    Returns:
        - dates: Array of date statistics items
        - total_dates: Count of dates with data
        - total_files: Sum of all files across dates
        - total_success: Sum of successfully processed files
        - total_failed: Sum of failed files
    """
    try:
        stats = db.get_date_statistics(start_date, end_date)
        
        # Calculate aggregate totals
        total_files = sum(s['total_files'] for s in stats)
        total_success = sum(s['processed_files'] for s in stats)
        total_failed = sum(s['failed_files'] for s in stats)
        
        date_items = [DateStatItem(**s) for s in stats]
        
        return DateStatsResponse(
            dates=date_items,
            total_dates=len(date_items),
            total_files=total_files,
            total_success=total_success,
            total_failed=total_failed
        )
    except Exception as e:
        logger.error(f"Failed to get date statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
