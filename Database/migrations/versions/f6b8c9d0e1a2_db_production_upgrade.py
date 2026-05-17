"""db production upgrade

Revision ID: f6b8c9d0e1a2
Revises: d876b980dc9a
Create Date: 2026-05-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = "f6b8c9d0e1a2"
down_revision: Union[str, Sequence[str], None] = "d876b980dc9a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    op.execute(f"""
        SET @drop_index_sql = (
            SELECT IF(
                COUNT(*) > 0,
                'ALTER TABLE `{table_name}` DROP INDEX `{index_name}`',
                'SELECT 1'
            )
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = '{table_name}'
              AND index_name = '{index_name}'
        )
    """)
    op.execute("PREPARE stmt FROM @drop_index_sql")
    op.execute("EXECUTE stmt")
    op.execute("DEALLOCATE PREPARE stmt")


def _drop_fk_if_exists(table_name: str, constraint_name: str) -> None:
    op.execute(f"""
        SET @drop_fk_sql = (
            SELECT IF(
                COUNT(*) > 0,
                'ALTER TABLE `{table_name}` DROP FOREIGN KEY `{constraint_name}`',
                'SELECT 1'
            )
            FROM information_schema.table_constraints
            WHERE table_schema = DATABASE()
              AND table_name = '{table_name}'
              AND constraint_name = '{constraint_name}'
              AND constraint_type = 'FOREIGN KEY'
        )
    """)
    op.execute("PREPARE stmt FROM @drop_fk_sql")
    op.execute("EXECUTE stmt")
    op.execute("DEALLOCATE PREPARE stmt")


def _create_index_if_missing(table_name: str, index_name: str, columns_sql: str) -> None:
    op.execute(f"""
        SET @create_index_sql = (
            SELECT IF(
                COUNT(*) = 0,
                'CREATE INDEX `{index_name}` ON `{table_name}` ({columns_sql})',
                'SELECT 1'
            )
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = '{table_name}'
              AND index_name = '{index_name}'
        )
    """)
    op.execute("PREPARE stmt FROM @create_index_sql")
    op.execute("EXECUTE stmt")
    op.execute("DEALLOCATE PREPARE stmt")


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE chat_messages REMOVE PARTITIONING")
    op.execute("ALTER TABLE chat_messages DROP PRIMARY KEY, ADD PRIMARY KEY (id)")
    _create_index_if_missing("sessions", "idx_sessions_user_fk", "`user_id`")

    for table_name, index_name in [
        ("sessions", "idx_user_activity"),
        ("sessions", "idx_user_active"),
        ("sessions", "idx_active_sessions_by_user"),
        ("chat_messages", "idx_session_time"),
        ("chat_messages", "idx_user_session"),
        ("chat_messages", "idx_recent_messages"),
        ("chat_attachments", "idx_message_attachment"),
        ("uploaded_files", "idx_user_files"),
        ("uploaded_files", "idx_filename_search"),
        ("checkpoints", "idx_thread_time"),
        ("checkpoint_writes", "idx_checkpoint"),
    ]:
        _drop_index_if_exists(table_name, index_name)

    op.execute("""
        CREATE INDEX idx_sessions_user_archived_activity
        ON sessions (user_id, is_archived, last_activity_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_chat_messages_user_session_created_id
        ON chat_messages (user_id, session_id, created_at DESC, id)
    """)
    op.execute("""
        CREATE INDEX idx_chat_messages_session_created_id
        ON chat_messages (session_id, created_at, id)
    """)
    op.execute("""
        CREATE INDEX idx_chat_attachments_message_type
        ON chat_attachments (message_id, attachment_type)
    """)
    op.execute("""
        CREATE INDEX idx_uploaded_files_user_accessed
        ON uploaded_files (user_id, last_accessed_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_uploaded_files_user_filename_accessed
        ON uploaded_files (user_id, original_filename, last_accessed_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_checkpoints_thread_ns_created
        ON checkpoints (thread_id, checkpoint_ns, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX idx_checkpoint_writes_checkpoint
        ON checkpoint_writes (thread_id, checkpoint_ns, checkpoint_id)
    """)

    op.execute("""
        ALTER TABLE chat_messages
        ADD CONSTRAINT fk_chat_messages_session
        FOREIGN KEY (session_id) REFERENCES sessions(id)
        ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE chat_messages
        ADD CONSTRAINT fk_chat_messages_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE chat_attachments
        ADD CONSTRAINT fk_chat_attachments_message
        FOREIGN KEY (message_id) REFERENCES chat_messages(id)
        ON DELETE CASCADE
    """)
    op.execute("""
        ALTER TABLE checkpoint_writes
        ADD CONSTRAINT fk_checkpoint_writes_checkpoint
        FOREIGN KEY (thread_id, checkpoint_ns, checkpoint_id)
        REFERENCES checkpoints(thread_id, checkpoint_ns, checkpoint_id)
        ON DELETE CASCADE
    """)


def downgrade() -> None:
    """Downgrade schema."""
    for table_name, constraint_name in [
        ("checkpoint_writes", "fk_checkpoint_writes_checkpoint"),
        ("chat_attachments", "fk_chat_attachments_message"),
        ("chat_messages", "fk_chat_messages_user"),
        ("chat_messages", "fk_chat_messages_session"),
    ]:
        _drop_fk_if_exists(table_name, constraint_name)

    for table_name, index_name in [
        ("sessions", "idx_sessions_user_fk"),
        ("sessions", "idx_sessions_user_archived_activity"),
        ("chat_messages", "idx_chat_messages_user_session_created_id"),
        ("chat_messages", "idx_chat_messages_session_created_id"),
        ("chat_attachments", "idx_chat_attachments_message_type"),
        ("uploaded_files", "idx_uploaded_files_user_accessed"),
        ("uploaded_files", "idx_uploaded_files_user_filename_accessed"),
        ("checkpoints", "idx_checkpoints_thread_ns_created"),
        ("checkpoint_writes", "idx_checkpoint_writes_checkpoint"),
    ]:
        _drop_index_if_exists(table_name, index_name)

    op.execute("ALTER TABLE chat_messages DROP PRIMARY KEY, ADD PRIMARY KEY (id, created_at)")
    op.execute("""
        ALTER TABLE chat_messages
        PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
            PARTITION p_2024 VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
            PARTITION p_2025_q1 VALUES LESS THAN (UNIX_TIMESTAMP('2025-04-01')),
            PARTITION p_2025_q2 VALUES LESS THAN (UNIX_TIMESTAMP('2025-07-01')),
            PARTITION p_2025_q3 VALUES LESS THAN (UNIX_TIMESTAMP('2025-10-01')),
            PARTITION p_2025_q4 VALUES LESS THAN (UNIX_TIMESTAMP('2026-01-01')),
            PARTITION p_future VALUES LESS THAN MAXVALUE
        )
    """)
