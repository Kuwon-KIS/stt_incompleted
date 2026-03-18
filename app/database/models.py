"""Database models for SQLite."""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
import json


@dataclass
class BatchJob:
    """Model for batch_jobs table."""
    id: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    total_files: int = 0
    success_files: int = 0
    failed_files: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, handling datetime objects."""
        d = asdict(self)
        d['created_at'] = self.created_at.isoformat() if self.created_at else None
        d['started_at'] = self.started_at.isoformat() if self.started_at else None
        d['completed_at'] = self.completed_at.isoformat() if self.completed_at else None
        return d


@dataclass
class BatchResult:
    """Model for batch_results table."""
    id: Optional[int] = None
    job_id: str = ""
    file_date: str = ""  # YYYYMMDD
    filename: str = ""
    success: bool = True
    text_content: Optional[str] = None
    category: Optional[str] = None
    summary: Optional[str] = None
    omission_num: int = 0
    detected_issues: List[Dict[str, str]] = field(default_factory=list)
    error_message: Optional[str] = None
    processing_time_ms: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d['detected_issues'] = self.detected_issues  # JSON 문자열이 아니라 리스트로 유지
        d['created_at'] = self.created_at.isoformat()
        d['date'] = self.file_date  # alias: date -> file_date
        return d


@dataclass
class DateStatus:
    """Model for date_status table."""
    id: Optional[int] = None
    date: str = ""  # YYYYMMDD
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    last_processed: Optional[datetime] = None
    status: str = "ready"  # 'ready', 'incomplete', 'done', 'failed'
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = asdict(self)
        d['last_processed'] = self.last_processed.isoformat() if self.last_processed else None
        d['created_at'] = self.created_at.isoformat()
        d['updated_at'] = self.updated_at.isoformat()
        return d
