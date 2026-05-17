"""
数据库轻量监控查询。
"""

from __future__ import annotations

from typing import Any

from app.db import get_read_connection, get_replica_status
from config.settings import settings


def _status_values(cursor, names: list[str]) -> dict[str, int]:
    placeholders = ", ".join(["%s"] * len(names))
    cursor.execute(f"SHOW GLOBAL STATUS WHERE Variable_name IN ({placeholders})", names)
    return {row["Variable_name"]: int(row["Value"]) for row in cursor.fetchall()}


def _max_connections(cursor) -> int | None:
    cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
    row = cursor.fetchone()
    return int(row["Value"]) if row else None


def _replica_status() -> dict[str, Any] | None:
    if not settings.MYSQL_READ_HOSTS:
        return None
    row = get_replica_status(settings.MYSQL_READ_HOSTS[0])
    if not row:
        return None
    return {
        "Replica_IO_Running": row.get("Replica_IO_Running"),
        "Replica_SQL_Running": row.get("Replica_SQL_Running"),
        "Seconds_Behind_Source": row.get("Seconds_Behind_Source"),
        "Last_IO_Error": row.get("Last_IO_Error"),
        "Last_SQL_Error": row.get("Last_SQL_Error"),
    }


def _table_sizes(cursor) -> list[dict[str, Any]]:
    cursor.execute("""
        SELECT
            table_name,
            table_rows,
            data_length,
            index_length,
            data_length + index_length AS total_length
        FROM information_schema.tables
        WHERE table_schema = DATABASE()
        ORDER BY total_length DESC
    """)
    return cursor.fetchall()


def get_db_health() -> dict[str, Any]:
    with get_read_connection(consistency="eventual") as conn:
        cursor = conn.cursor(dictionary=True)
        status = _status_values(cursor, ["Threads_connected", "Threads_running", "Slow_queries"])
        return {
            "connections": {
                "Threads_connected": status.get("Threads_connected"),
                "Threads_running": status.get("Threads_running"),
                "max_connections": _max_connections(cursor),
            },
            "slow_queries": status.get("Slow_queries"),
            "replica": _replica_status(),
            "tables": _table_sizes(cursor),
        }


def get_slow_query_summary(limit: int = 20) -> dict[str, Any]:
    with get_read_connection(consistency="eventual") as conn:
        cursor = conn.cursor(dictionary=True)
        status = _status_values(cursor, ["Slow_queries"])
        try:
            cursor.execute("""
                SELECT
                    DIGEST_TEXT AS digest_text,
                    COUNT_STAR AS count_star,
                    ROUND(SUM_TIMER_WAIT / 1000000000000, 6) AS total_seconds,
                    ROUND(AVG_TIMER_WAIT / 1000000000000, 6) AS avg_seconds,
                    SUM_ROWS_EXAMINED AS rows_examined,
                    SUM_ROWS_SENT AS rows_sent
                FROM performance_schema.events_statements_summary_by_digest
                WHERE SCHEMA_NAME = DATABASE()
                  AND DIGEST_TEXT IS NOT NULL
                ORDER BY SUM_TIMER_WAIT DESC
                LIMIT %s
            """, (limit,))
            top_statements = cursor.fetchall()
        except Exception as exc:
            top_statements = []
            return {
                "Slow_queries": status.get("Slow_queries"),
                "top_statements": top_statements,
                "warning": f"无法读取 performance_schema 摘要: {exc}",
            }

        return {
            "Slow_queries": status.get("Slow_queries"),
            "top_statements": top_statements,
        }
