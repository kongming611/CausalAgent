"""create core schema

Revision ID: 1a2b3c4d5e6f
Revises:
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login_at TIMESTAMP DEFAULT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            INDEX idx_username (username),
            INDEX idx_active_users (is_active, last_login_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE TABLE sessions (
            id VARCHAR(36) PRIMARY KEY COMMENT 'UUID格式的会话ID',
            user_id INT NOT NULL,
            title VARCHAR(500) DEFAULT NULL COMMENT '会话标题，可以是第一条消息的摘要',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            message_count INT DEFAULT 0 COMMENT '该会话的消息总数',
            is_archived BOOLEAN DEFAULT FALSE COMMENT '是否已归档',
            archived_at TIMESTAMP DEFAULT NULL,
            CONSTRAINT fk_sessions_user
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            INDEX idx_user_activity (user_id, last_activity_at DESC),
            INDEX idx_user_active (user_id, is_archived, last_activity_at DESC),
            INDEX idx_archive_cleanup (is_archived, archived_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE TABLE chat_messages (
            id BIGINT AUTO_INCREMENT,
            session_id VARCHAR(36) NOT NULL,
            user_id INT NOT NULL,
            message_type ENUM('user', 'ai') NOT NULL COMMENT '消息类型：用户或AI',
            content TEXT NOT NULL COMMENT '消息内容（纯文本或简单JSON）',
            has_attachment BOOLEAN DEFAULT FALSE COMMENT '是否有大型附件数据',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (id, created_at),
            INDEX idx_session_time (session_id, created_at),
            INDEX idx_user_session (user_id, session_id, created_at),
            INDEX idx_message_type (message_type, created_at),
            INDEX idx_attachment_flag (has_attachment)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
            PARTITION p_2024 VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
            PARTITION p_2025_q1 VALUES LESS THAN (UNIX_TIMESTAMP('2025-04-01')),
            PARTITION p_2025_q2 VALUES LESS THAN (UNIX_TIMESTAMP('2025-07-01')),
            PARTITION p_2025_q3 VALUES LESS THAN (UNIX_TIMESTAMP('2025-10-01')),
            PARTITION p_2025_q4 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
            PARTITION p_future VALUES LESS THAN MAXVALUE
        )
    """)
    op.execute("""
        CREATE TABLE chat_attachments (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            message_id BIGINT NOT NULL,
            attachment_type ENUM('causal_graph', 'analysis_result', 'file_content', 'other') NOT NULL,
            content LONGTEXT NOT NULL COMMENT '大型JSON数据或其他结构化内容',
            content_size INT GENERATED ALWAYS AS (LENGTH(content)) STORED COMMENT '内容大小，用于监控',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_message_attachment (message_id, attachment_type),
            INDEX idx_type_size (attachment_type, content_size),
            INDEX idx_size_cleanup (content_size, created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE TABLE uploaded_files (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            filename VARCHAR(255) NOT NULL,
            original_filename VARCHAR(255) NOT NULL COMMENT '用户上传时的原始文件名',
            mime_type VARCHAR(100) NOT NULL,
            file_size BIGINT NOT NULL COMMENT '文件大小（字节）',
            file_hash VARCHAR(64) NOT NULL COMMENT 'SHA-256哈希，用于去重',
            file_content LONGBLOB NOT NULL,
            upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            access_count INT DEFAULT 0 COMMENT '访问次数',
            CONSTRAINT fk_uploaded_files_user
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE KEY unique_user_hash (user_id, file_hash),
            INDEX idx_user_files (user_id, upload_timestamp DESC),
            INDEX idx_filename_search (user_id, filename),
            INDEX idx_size_cleanup (file_size, last_accessed_at),
            INDEX idx_hash_dedup (file_hash)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE TABLE archived_sessions (
            id VARCHAR(36) PRIMARY KEY,
            user_id INT NOT NULL,
            original_session_data JSON NOT NULL COMMENT '原始会话的元数据',
            message_count INT NOT NULL,
            archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            archive_reason ENUM('user_request', 'auto_cleanup', 'admin_action') DEFAULT 'auto_cleanup',
            compressed_data LONGBLOB COMMENT '压缩后的会话数据',
            INDEX idx_user_archived (user_id, archived_at),
            INDEX idx_cleanup_schedule (archive_reason, archived_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """)
    op.execute("""
        CREATE INDEX idx_active_sessions_by_user
        ON sessions (user_id, is_archived, last_activity_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_recent_messages
        ON chat_messages (created_at DESC, user_id, session_id)
    """)
    op.execute("""
        CREATE INDEX idx_large_attachments
        ON chat_attachments (content_size DESC, created_at)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS archived_sessions")
    op.execute("DROP TABLE IF EXISTS uploaded_files")
    op.execute("DROP TABLE IF EXISTS chat_attachments")
    op.execute("DROP TABLE IF EXISTS chat_messages")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
