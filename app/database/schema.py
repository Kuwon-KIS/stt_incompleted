"""Database schema and initialization."""

SQL_SCHEMA = """
-- Batch jobs table
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
);

-- Batch results table (individual file results)
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
);

-- Date processing status table
-- Status values: 'ready' (준비), 'done' (완료), 'incomplete' (불완전), 'failed' (실패)
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
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_results_job_id ON batch_results(job_id);
CREATE INDEX IF NOT EXISTS idx_batch_results_file_date ON batch_results(file_date);
CREATE INDEX IF NOT EXISTS idx_date_status_date ON date_status(date);
"""


def get_schema() -> str:
    """Get database schema SQL."""
    return SQL_SCHEMA
