"""
管理接口路由。
"""

from flask import Blueprint, jsonify, session
import logging

from Database.monitoring import get_db_health, get_slow_query_summary
from app.auth.session_guard import get_current_session_user


admin_bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _require_login():
    return get_current_session_user() is not None


@admin_bp.route("/db/health")
def db_health():
    if not _require_login():
        return jsonify({"success": False, "error": "用户未登录或会话已过期"}), 401
    try:
        return jsonify({"success": True, "data": get_db_health()})
    except Exception as exc:
        logging.error("读取数据库健康状态失败: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": "读取数据库健康状态失败"}), 500


@admin_bp.route("/db/slow-queries")
def db_slow_queries():
    if not _require_login():
        return jsonify({"success": False, "error": "用户未登录或会话已过期"}), 401
    try:
        return jsonify({"success": True, "data": get_slow_query_summary()})
    except Exception as exc:
        logging.error("读取慢查询摘要失败: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": "读取慢查询摘要失败"}), 500
