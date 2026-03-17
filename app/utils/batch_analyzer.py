"""Batch case analysis utility for SELECT_TARGET feature.

Analyzes user-selected date ranges against completed jobs to determine
the optimal processing strategy.
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BatchAnalysisOption:
    """Represents a processing option for batch analysis."""
    
    def __init__(self, option_id: str, label: str, description: str, action_config: Dict[str, Any]):
        self.option_id = option_id
        self.label = label
        self.description = description
        self.action_config = action_config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "option_id": self.option_id,
            "label": self.label,
            "description": self.description,
            "action_config": self.action_config
        }


class BatchAnalysisResult:
    """Result of batch case analysis."""
    
    def __init__(
        self,
        case: str,
        user_range: Dict[str, str],
        completed_range: Optional[Dict[str, str]],
        overlap_dates: List[str],
        new_dates: List[str],
        options: List[BatchAnalysisOption]
    ):
        self.case = case
        self.user_range = user_range
        self.completed_range = completed_range
        self.overlap_dates = overlap_dates
        self.new_dates = new_dates
        self.options = options
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return {
            "case": self.case,
            "user_range": self.user_range,
            "completed_range": self.completed_range,
            "overlap_dates": self.overlap_dates,
            "new_dates": self.new_dates,
            "options": [opt.to_dict() for opt in self.options]
        }


def analyze_batch_case(
    start_date: str,
    end_date: str,
    available_dates: List[str],
    completed_dates: List[str]
) -> BatchAnalysisResult:
    """Analyze batch case for user-selected date range.
    
    Determines which dates fall within user selection and which are already completed,
    then classifies into one of 4 cases (full_overlap, partial_overlap, no_overlap, no_data).
    
    Args:
        start_date: User selected start date (YYYYMMDD)
        end_date: User selected end date (YYYYMMDD)
        available_dates: List of available dates from SFTP (YYYYMMDD format, sorted)
        completed_dates: List of completed dates from DB (YYYYMMDD format)
        
    Returns:
        BatchAnalysisResult with case classification and processing options
        
    Raises:
        ValueError: If date range is invalid or no available dates
    """
    logger.info(f"Analyzing batch case: range=[{start_date}, {end_date}]")
    
    # Validate inputs
    _validate_date_range(start_date, end_date)
    
    # Get dates within user range
    user_dates = [d for d in available_dates if start_date <= d <= end_date]
    
    logger.info(f"User range contains {len(user_dates)} dates: {user_dates}")
    logger.info(f"Completed dates: {completed_dates}")
    
    # Determine overlaps
    overlap_dates = [d for d in user_dates if d in completed_dates]
    new_dates = [d for d in user_dates if d not in completed_dates]
    
    # Get completed date range (min/max of completed dates in user range)
    completed_range = _get_date_range_dict(overlap_dates) if overlap_dates else None
    
    user_range = {"start_date": start_date, "end_date": end_date}
    
    # Classify case and generate options
    if not user_dates:
        # Case 4: No data
        case = "no_data"
        options = []
        logger.warning(f"Case: no_data - no available dates in range")
        
    elif len(overlap_dates) == 0:
        # Case 3: No overlap
        case = "no_overlap"
        options = []  # Auto-process, no options needed
        logger.info(f"Case: no_overlap - {len(new_dates)} new dates to process")
        
    elif len(overlap_dates) == len(user_dates):
        # Case 1: Full overlap - all dates are completed
        case = "full_overlap"
        options = _generate_full_overlap_options()
        logger.info(f"Case: full_overlap - all {len(user_dates)} dates already completed")
        
    else:
        # Case 2: Partial overlap
        case = "partial_overlap"
        options = _generate_partial_overlap_options(new_dates, user_range)
        logger.info(f"Case: partial_overlap - {len(overlap_dates)} completed, {len(new_dates)} new")
    
    result = BatchAnalysisResult(
        case=case,
        user_range=user_range,
        completed_range=completed_range,
        overlap_dates=overlap_dates,
        new_dates=new_dates,
        options=options
    )
    
    return result


def _validate_date_range(start_date: str, end_date: str) -> None:
    """Validate date range parameters.
    
    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        
    Raises:
        ValueError: If dates are invalid or start_date > end_date
    """
    try:
        start = datetime.strptime(start_date, "%Y%m%d")
        end = datetime.strptime(end_date, "%Y%m%d")
        
        if start > end:
            raise ValueError(f"Start date {start_date} must be <= end date {end_date}")
    
    except ValueError as e:
        logger.error(f"Invalid date format or range: {e}")
        raise


def _get_date_range_dict(dates: List[str]) -> Dict[str, str]:
    """Get min/max date range from list of dates.
    
    Args:
        dates: List of dates in YYYYMMDD format
        
    Returns:
        Dict with start_date (min) and end_date (max)
    """
    if not dates:
        return None
    
    sorted_dates = sorted(dates)
    return {"start_date": sorted_dates[0], "end_date": sorted_dates[-1]}


def _generate_full_overlap_options() -> List[BatchAnalysisOption]:
    """Generate options for full_overlap case (all dates completed).
    
    Returns:
        List of processing options
    """
    options = [
        BatchAnalysisOption(
            option_id="reprocess",
            label="재처리",
            description="기존 완료된 작업을 다시 처리합니다",
            action_config={
                "type": "reprocess_all",
                "force": True  # Force re-process
            }
        ),
        BatchAnalysisOption(
            option_id="view_history",
            label="이전 기록 보기",
            description="기존에 처리한 결과를 확인합니다",
            action_config={
                "type": "view_history"
            }
        )
    ]
    return options


def _generate_partial_overlap_options(new_dates: List[str], user_range: Dict[str, str]) -> List[BatchAnalysisOption]:
    """Generate options for partial_overlap case (some dates completed).
    
    Args:
        new_dates: List of dates that haven't been processed
        user_range: User selected date range
        
    Returns:
        List of processing options
    """
    new_date_count = len(new_dates)
    new_dates_str = f"{min(new_dates)}~{max(new_dates)}" if new_dates else "없음"
    
    options = [
        BatchAnalysisOption(
            option_id="process_new",
            label="새로운 부분만 처리",
            description=f"미처리된 날짜만 처리합니다 ({new_date_count}일: {new_dates_str})",
            action_config={
                "type": "process_new",
                "start_date": min(new_dates),
                "end_date": max(new_dates)
            }
        ),
        BatchAnalysisOption(
            option_id="reprocess_all",
            label="전체 재처리",
            description=f"선택한 전체 범위를 다시 처리합니다 ({user_range['start_date']}~{user_range['end_date']})",
            action_config={
                "type": "reprocess_all",
                "start_date": user_range["start_date"],
                "end_date": user_range["end_date"],
                "force": True
            }
        )
    ]
    return options
