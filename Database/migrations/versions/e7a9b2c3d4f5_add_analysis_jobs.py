"""add analysis jobs

Revision ID: e7a9b2c3d4f5
Revises: f6b8c9d0e1a2
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e7a9b2c3d4f5"
down_revision: Union[str, Sequence[str], None] = "f6b8c9d0e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE analysis_jobs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_id VARCHAR(36) NOT NULL,
            user_id INT NOT NULL,
            session_id VARCHAR(36) NOT NULL,
            message MEDIUMTEXT NOT NULL,
            status ENUM('queued', 'running', 'succeeded', 'failed', 'canceled')
                NOT NULL DEFAULT 'queued',
            result_json JSON DEFAULT NULL,
            error_message TEXT DEFAULT NULL,
            worker_id VARCHAR(128) DEFAULT NULL,
            locked_at DATETIME(6) DEFAULT NULL,
            heartbeat_at DATETIME(6) DEFAULT NULL,
            attempt_count INT NOT NULL DEFAULT 0,
            max_attempts INT NOT NULL DEFAULT 3,
            last_error TEXT DEFAULT NULL,
            chat_saved_at DATETIME(6) DEFAULT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            started_at DATETIME(6) DEFAULT NULL,
            finished_at DATETIME(6) DEFAULT NULL,
            active_session_key VARCHAR(128) DEFAULT NULL,
            UNIQUE KEY uq_analysis_jobs_job_id (job_id),
            UNIQUE KEY uq_analysis_jobs_active_session (active_session_key),
            INDEX idx_analysis_jobs_status_created (status, created_at),
            INDEX idx_analysis_jobs_status_heartbeat (status, heartbeat_at),
            INDEX idx_analysis_jobs_user_session_status (user_id, session_id, status),
            INDEX idx_analysis_jobs_user_created (user_id, created_at),
            CONSTRAINT fk_analysis_jobs_user
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            CONSTRAINT fk_analysis_jobs_session
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE TABLE analysis_job_events (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            job_id VARCHAR(36) NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            payload_json JSON NOT NULL,
            created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            INDEX idx_analysis_job_events_job_id (job_id, id),
            CONSTRAINT fk_analysis_job_events_job
                FOREIGN KEY (job_id) REFERENCES analysis_jobs(job_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analysis_job_events")
    op.execute("DROP TABLE IF EXISTS analysis_jobs")
