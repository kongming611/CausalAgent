"""
会话用户校验工具。
"""

from flask import session
import logging


def find_user_by_id(user_id):
    from app.auth.service import find_user_by_id as _find_user_by_id

    return _find_user_by_id(user_id)


def get_current_session_user():
    """
    返回当前会话对应的真实用户。

    如果浏览器里还保留着旧 session，但当前数据库中该用户已不存在，
    则主动清空 session，避免后续请求继续带着过期 user_id 写库。
    """
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = find_user_by_id(user_id)
    if not user:
        logging.warning("检测到失效会话，用户 ID %s 在当前数据库中不存在，已清空会话。", user_id)
        session.clear()
        return None

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    return user
