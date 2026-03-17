"""Database manager for SQLite operations."""

import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

from .models import BatchJob, BatchResult, DateStatus

logger = logging.getLogger(__name__)


class DatabaseManager:
    """SQLite database manager for STT job persistence."""

    def __init__(self, db_path: str = "app/data/stt_jobs.db"):
        """Initialize database manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self.init_db()

    def _ensure_db_dir(self) -> None:
        """Ensure database directory exists."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Database directory ready: {db_dir}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Create batch_jobs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    total_files INTEGER DEFAULT 0,
                    success_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0
                )
            """)

            # Create batch_results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS batch_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    file_date TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    text_content TEXT,
                    category TEXT,
                    summary TEXT,
                    omission_num INTEGER,
                    detected_issues JSON,
                    error_message TEXT,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (job_id) REFERENCES batch_jobs(id)
                )
            """)

            # Create date_status table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS date_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    total_files INTEGER DEFAULT 0,
                    processed_files INTEGER DEFAULT 0,
                    failed_files INTEGER DEFAULT 0,
                    last_processed TIMESTAMP,
                    status TEXT DEFAULT 'ready',
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)

            # Create indexes for better query performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_jobs_status 
                ON batch_jobs(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_results_job_id 
                ON batch_results(job_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_batch_results_file_date 
                ON batch_results(file_date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_date_status_date 
                ON date_status(date)
            """)

            conn.commit()
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
        finally:
            conn.close()

    def reset_db(self) -> None:
        """Reset database - drop all tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DROP TABLE IF EXISTS batch_results")
            cursor.execute("DROP TABLE IF EXISTS batch_jobs")
            cursor.execute("DROP TABLE IF EXISTS date_status")
            conn.commit()
            logger.warning("Database reset completed")
            self.init_db()
        except Exception as e:
            logger.error(f"Database reset failed: {e}")
            raise
        finally:
            conn.close()

    # ===== BatchJob Operations =====

    def create_job(self, job: BatchJob) -> None:
        """Create new batch job."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO batch_jobs 
                (id, status, start_date, end_date, created_at, started_at, 
                 completed_at, error_message, total_files, success_files, failed_files)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job.id, job.status, job.start_date, job.end_date, job.created_at,
                job.started_at, job.completed_at, job.error_message,
                job.total_files, job.success_files, job.failed_files
            ))
            conn.commit()
            logger.info(f"Job created: {job.id}")
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise
        finally:
            conn.close()

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get batch job by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM batch_jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()

            if row:
                return BatchJob(
                    id=row['id'],
                    status=row['status'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    error_message=row['error_message'],
                    total_files=row['total_files'],
                    success_files=row['success_files'],
                    failed_files=row['failed_files']
                )
            return None
        except Exception as e:
            logger.error(f"Failed to get job: {e}")
            raise
        finally:
            conn.close()

    def update_job_status(self, job_id: str, status: str, 
                         error_message: Optional[str] = None) -> None:
        """Update job status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            updates = {"status": status, "updated_at": datetime.now()}
            if error_message:
                updates["error_message"] = error_message
            if status == "running":
                updates["started_at"] = datetime.now()
            elif status in ["completed", "failed"]:
                updates["completed_at"] = datetime.now()

            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values()) + [job_id]

            cursor.execute(f"UPDATE batch_jobs SET {set_clause} WHERE id = ?", values)
            conn.commit()
            logger.info(f"Job {job_id} status updated to {status}")
        except Exception as e:
            logger.error(f"Failed to update job status: {e}")
            raise
        finally:
            conn.close()

    def update_job_stats(self, job_id: str, total: int, success: int, failed: int) -> None:
        """Update job statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE batch_jobs 
                SET total_files = ?, success_files = ?, failed_files = ?
                WHERE id = ?
            """, (total, success, failed, job_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update job stats: {e}")
            raise
        finally:
            conn.close()

    # ===== BatchResult Operations =====

    def create_result(self, result: BatchResult) -> int:
        """Create batch result and return ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO batch_results 
                (job_id, file_date, filename, success, text_content, category, 
                 summary, omission_num, detected_issues, error_message, processing_time_ms, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.job_id, result.file_date, result.filename, result.success,
                result.text_content, result.category, result.summary, result.omission_num,
                json.dumps(result.detected_issues), result.error_message,
                result.processing_time_ms, result.created_at
            ))
            conn.commit()
            result_id = cursor.lastrowid
            logger.info(f"Result created: {result_id} for job {result.job_id}")
            return result_id
        except Exception as e:
            logger.error(f"Failed to create result: {e}")
            raise
        finally:
            conn.close()

    def get_results_by_job(self, job_id: str) -> List[BatchResult]:
        """Get all results for a job."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM batch_results WHERE job_id = ? ORDER BY created_at DESC
            """, (job_id,))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                results.append(BatchResult(
                    id=row['id'],
                    job_id=row['job_id'],
                    file_date=row['file_date'],
                    filename=row['filename'],
                    success=bool(row['success']),
                    text_content=row['text_content'],
                    category=row['category'],
                    summary=row['summary'],
                    omission_num=row['omission_num'],
                    detected_issues=json.loads(row['detected_issues']) if row['detected_issues'] else [],
                    error_message=row['error_message'],
                    processing_time_ms=row['processing_time_ms'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
            return results
        except Exception as e:
            logger.error(f"Failed to get results: {e}")
            raise
        finally:
            conn.close()

    # ===== DateStatus Operations =====

    def get_or_create_date_status(self, date: str) -> DateStatus:
        """Get or create date status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM date_status WHERE date = ?", (date,))
            row = cursor.fetchone()

            if row:
                return DateStatus(
                    id=row['id'],
                    date=row['date'],
                    total_files=row['total_files'],
                    processed_files=row['processed_files'],
                    failed_files=row['failed_files'],
                    last_processed=datetime.fromisoformat(row['last_processed']) if row['last_processed'] else None,
                    status=row['status'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )

            # Create new
            now = datetime.now()
            cursor.execute("""
                INSERT INTO date_status (date, created_at, updated_at)
                VALUES (?, ?, ?)
            """, (date, now, now))
            conn.commit()

            return DateStatus(date=date, created_at=now, updated_at=now)
        except Exception as e:
            logger.error(f"Failed to get/create date status: {e}")
            raise
        finally:
            conn.close()

    def update_date_status(self, date: str, total: int, processed: int, 
                          failed: int, status: str) -> None:
        """Update date status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE date_status 
                SET total_files = ?, processed_files = ?, failed_files = ?, 
                    status = ?, last_processed = ?, updated_at = ?
                WHERE date = ?
            """, (total, processed, failed, status, datetime.now(), datetime.now(), date))
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to update date status: {e}")
            raise
        finally:
            conn.close()

    def get_month_status(self, year: int, month: int) -> Dict[str, Dict[str, Any]]:
        """Get calendar status for a month."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            month_str = f"{year}{month:02d}"
            cursor.execute("""
                SELECT * FROM date_status WHERE date LIKE ? ORDER BY date
            """, (f"{month_str}%",))
            rows = cursor.fetchall()

            result = {}
            for row in rows:
                result[row['date']] = {
                    'status': row['status'],
                    'total': row['total_files'],
                    'processed': row['processed_files'],
                    'failed': row['failed_files']
                }
            return result
        except Exception as e:
            logger.error(f"Failed to get month status: {e}")
            raise
        finally:
            conn.close()

    def get_db_status(self) -> Dict[str, Any]:
        """Get database status."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) as count FROM batch_jobs")
            jobs_count = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM batch_results")
            results_count = cursor.fetchone()['count']

            cursor.execute("SELECT COUNT(*) as count FROM date_status")
            dates_count = cursor.fetchone()['count']

            return {
                'db_file': self.db_path,
                'jobs': jobs_count,
                'results': results_count,
                'dates': dates_count,
                'initialized': True
            }
        except Exception as e:
            logger.error(f"Failed to get db status: {e}")
            raise
        finally:
            conn.close()
