"""Admin API routes for database management."""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

from app.database import DatabaseManager
from app.config import config
from app.sftp_client import create_sftp_client
from app.utils.batch_analyzer import analyze_batch_case

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


class DateRangeResponse(BaseModel):
    """Date range response."""
    min_date: str  # YYYYMMDD format
    max_date: str  # YYYYMMDD format
    available_dates: List[str]  # Sorted list of available dates
    source: str  # "local" | "sftp"
    test_mode: bool  # Whether TEST_MODE is active


class BatchAnalysisOption(BaseModel):
    """Batch processing option."""
    option_id: str  # e.g., "reprocess", "view_history", "process_new"
    label: str
    description: str
    action_config: Dict[str, Any]


class BatchAnalysisRequest(BaseModel):
    """Batch analysis request."""
    start_date: str  # YYYYMMDD format
    end_date: str    # YYYYMMDD format


class BatchAnalysisResponse(BaseModel):
    """Batch analysis response."""
    case: str  # "full_overlap" | "partial_overlap" | "no_overlap" | "no_data"
    user_range: Dict[str, str]  # {start_date, end_date}
    completed_range: Optional[Dict[str, str]]  # {start_date, end_date} or null
    overlap_dates: List[str]  # Dates that are already completed
    new_dates: List[str]      # Dates that are not yet processed
    options: List[BatchAnalysisOption]  # Processing options for this case


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


@router.get("/date-range", response_model=DateRangeResponse)
async def get_date_range():
    """Get available date range from SFTP or Mock data.
    
    Returns the minimum and maximum dates available for batch processing,
    along with a list of all available dates.
    
    For local environment: returns mock dates (past 2 days + today)
    For prod/dev environment: queries SFTP root directory for date folders
    
    If SFTP fails and TEST_MODE=true, falls back to mock data.
    """
    try:
        if config.APP_ENV == "local":
            # Local environment: use mock data
            from app.sftp_client import MockSFTPClient
            client = MockSFTPClient(
                host=config.SFTP_HOST or "mock",
                username=config.SFTP_USERNAME,
                password=config.SFTP_PASSWORD
            )
            available_dates = client.get_available_dates()
            source = "local"
            
        else:
            # Production/Dev environment: try real SFTP first
            available_dates = None
            source = "sftp"
            
            try:
                client = create_sftp_client(
                    host=config.SFTP_HOST,
                    port=config.SFTP_PORT,
                    username=config.SFTP_USERNAME,
                    password=config.SFTP_PASSWORD,
                    pkey=config.SFTP_KEY
                )
                available_dates = client.get_available_dates(root_path=config.SFTP_ROOT_PATH)
                client.close()
                logger.info(f"Successfully retrieved {len(available_dates)} dates from SFTP")
                
            except Exception as e:
                logger.warning(f"SFTP connection failed: {e}")
                
                if config.TEST_MODE:
                    # TEST_MODE enabled: fallback to mock data
                    logger.warning("TEST_MODE=true, using mock data as fallback")
                    from app.sftp_client import MockSFTPClient
                    client = MockSFTPClient(
                        host=config.SFTP_HOST or "mock",
                        username=config.SFTP_USERNAME,
                        password=config.SFTP_PASSWORD
                    )
                    available_dates = client.get_available_dates()
                    source = "local"
                else:
                    # No TEST_MODE: raise error
                    logger.error(f"SFTP connection failed and TEST_MODE={config.TEST_MODE}")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"SFTP 연결 실패: {str(e)}"
                    )
        
        if not available_dates:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="처리 가능한 날짜가 없습니다"
            )
        
        return DateRangeResponse(
            min_date=min(available_dates),
            max_date=max(available_dates),
            available_dates=available_dates,
            source=source,
            test_mode=config.TEST_MODE
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get date range: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"날짜 범위 조회 실패: {str(e)}"
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

@router.post("/batch-analysis", response_model=BatchAnalysisResponse)
async def analyze_batch(req: BatchAnalysisRequest):
    """Analyze batch processing case for user-selected date range.
    
    Compares user-selected date range against:
    1. Available dates (from SFTP or Mock)
    2. Completed dates (from database)
    
    Classifies into 4 cases and generates appropriate processing options:
    - full_overlap: All dates already processed → "재처리" or "이전 기록 보기"
    - partial_overlap: Some dates processed → "새로운 부분만 처리" or "전체 재처리"
    - no_overlap: No dates processed → Auto-process (no options)
    - no_data: No dates available in range → Error
    
    Args:
        start_date: User selected start date (YYYYMMDD)
        end_date: User selected end date (YYYYMMDD)
        
    Returns:
        BatchAnalysisResponse with case, options, and metadata
        
    Raises:
        HTTPException: If analysis fails
    """
    try:
        logger.info(f"Analyzing batch: [{req.start_date}, {req.end_date}]")
        
        # Step 1: Get available dates from SFTP/Mock
        available_dates = []
        try:
            if config.APP_ENV == "local":
                from app.sftp_client import MockSFTPClient
                client = MockSFTPClient(
                    host=config.SFTP_HOST or "mock",
                    username=config.SFTP_USERNAME,
                    password=config.SFTP_PASSWORD
                )
                available_dates = client.get_available_dates()
            else:
                try:
                    client = create_sftp_client(
                        host=config.SFTP_HOST,
                        port=config.SFTP_PORT,
                        username=config.SFTP_USERNAME,
                        password=config.SFTP_PASSWORD,
                        pkey=config.SFTP_KEY
                    )
                    available_dates = client.get_available_dates(root_path=config.SFTP_ROOT_PATH)
                    client.close()
                except Exception as e:
                    logger.warning(f"SFTP failed: {e}")
                    if config.TEST_MODE:
                        logger.warning("Using mock fallback (TEST_MODE=true)")
                        from app.sftp_client import MockSFTPClient
                        client = MockSFTPClient(
                            host=config.SFTP_HOST or "mock",
                            username=config.SFTP_USERNAME,
                            password=config.SFTP_PASSWORD
                        )
                        available_dates = client.get_available_dates()
                    else:
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail=f"SFTP 연결 실패: {str(e)}"
                        )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get available dates: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"날짜 범위 조회 실패: {str(e)}"
            )
        
        # Step 2: Get completed dates from database
        completed_dates = db.get_completed_date_range(req.start_date, req.end_date)
        logger.info(f"Completed dates in range: {completed_dates}")
        
        # Step 3: Analyze and classify case
        analysis = analyze_batch_case(
            start_date=req.start_date,
            end_date=req.end_date,
            available_dates=available_dates,
            completed_dates=completed_dates
        )
        
        # Step 4: Convert to response format
        response_options = [
            BatchAnalysisOption(
                option_id=opt.option_id,
                label=opt.label,
                description=opt.description,
                action_config=opt.action_config
            )
            for opt in analysis.options
        ]
        
        return BatchAnalysisResponse(
            case=analysis.case,
            user_range=analysis.user_range,
            completed_range=analysis.completed_range,
            overlap_dates=analysis.overlap_dates,
            new_dates=analysis.new_dates,
            options=response_options
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to analyze batch: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"배치 분석 실패: {str(e)}"
        )