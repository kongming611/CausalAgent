"""
数据库生产化升级前审计脚本。

只读检查，不修改数据。若发现 FAIL 项，应先修复数据再执行 alembic upgrade head。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import sys

import mysql.connector


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


def load_env() -> None:
    try:
        from dotenv import load_dotenv

        project_root = Path(__file__).resolve().parents[1]
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            logging.info("已从 %s 加载环境变量", env_path)
    except ImportError:
        logging.info("未安装 python-dotenv，使用系统环境变量")


def get_connection():
    load_env()
    host = os.environ.get("MYSQL_WRITE_HOST") or os.environ.get("MYSQL_HOST")
    user = os.environ.get("MYSQL_READ_USER") or os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_READ_PASSWORD") or os.environ.get("MYSQL_PASSWORD")
    required = {
        "MYSQL_HOST 或 MYSQL_WRITE_HOST": host,
        "MYSQL_READ_USER 或 MYSQL_USER": user,
        "MYSQL_READ_PASSWORD 或 MYSQL_PASSWORD": password,
        "MYSQL_DATABASE": os.environ.get("MYSQL_DATABASE"),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"缺少数据库环境变量: {missing}")

    return mysql.connector.connect(
        host=host,
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=user,
        password=password,
        database=os.environ["MYSQL_DATABASE"],
    )


def scalar(cursor, sql: str) -> int:
    cursor.execute(sql)
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def audit() -> list[tuple[str, str, int]]:
    checks: list[tuple[str, str, int]] = []
    with get_connection() as conn:
        cursor = conn.cursor()
        checks.append((
            "孤立 chat_messages.session_id",
            "FAIL",
            scalar(cursor, """
                SELECT COUNT(*)
                FROM chat_messages cm
                LEFT JOIN sessions s ON s.id = cm.session_id
                WHERE s.id IS NULL
            """),
        ))
        checks.append((
            "孤立 chat_messages.user_id",
            "FAIL",
            scalar(cursor, """
                SELECT COUNT(*)
                FROM chat_messages cm
                LEFT JOIN users u ON u.id = cm.user_id
                WHERE u.id IS NULL
            """),
        ))
        checks.append((
            "孤立 chat_attachments.message_id",
            "FAIL",
            scalar(cursor, """
                SELECT COUNT(*)
                FROM chat_attachments ca
                LEFT JOIN chat_messages cm ON cm.id = ca.message_id
                WHERE cm.id IS NULL
            """),
        ))
        checks.append((
            "非法 chat_attachments.attachment_type",
            "FAIL",
            scalar(cursor, """
                SELECT COUNT(*)
                FROM chat_attachments
                WHERE attachment_type NOT IN (
                    'causal_graph',
                    'analysis_result',
                    'file_content',
                    'other',
                    'visualization'
                )
            """),
        ))
        checks.append((
            "chat_messages 分区表",
            "INFO",
            scalar(cursor, """
                SELECT COUNT(*)
                FROM information_schema.partitions
                WHERE table_schema = DATABASE()
                  AND table_name = 'chat_messages'
                  AND partition_name IS NOT NULL
            """),
        ))
    return checks


def main() -> int:
    failures = 0
    for name, severity, count in audit():
        status = "PASS"
        if severity == "FAIL" and count > 0:
            status = "FAIL"
            failures += 1
        logging.info("%s | %s | count=%s", status, name, count)

    if failures:
        logging.error("审计未通过：发现 %s 类阻塞问题。请先修复数据。", failures)
        return 1
    logging.info("审计通过，可以继续执行 Alembic 迁移。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
