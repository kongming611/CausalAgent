"""
agent.routes - analysis job API 和 SSE 事件流。
"""

from __future__ import annotations

import json
import logging
import time

from flask import Blueprint, Response, jsonify, request, session, stream_with_context

from app.agent import core as agent_core
from app.agent import job_service
from app.auth.session_guard import get_current_session_user
from config.settings import settings

agent_bp = Blueprint('agent', __name__)


@agent_bp.route('/reset_session', methods=['POST'])
def reset_session():
    """
    重置指定会话的 agent 状态（清除 LangGraph checkpoint，保留聊天历史）。
    前端在收到 error 事件后调用此接口，允许用户重新发送消息。
    """
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': '用户未登录或会话已过期'}), 401

    data = request.json
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'success': False, 'error': '缺少 session_id'}), 400

    try:
        graph = agent_core.agent_graph
        if graph is None:
            return jsonify({'success': False, 'error': 'Agent 未初始化'}), 500

        checkpointer = graph.checkpointer
        if checkpointer is None:
            return jsonify({'success': False, 'error': 'Checkpointer 未启用'}), 500

        checkpointer.delete_thread(session_id)
        logging.info(f"[重置] 已清除会话 {session_id} 的 agent checkpoint")
        return jsonify({'success': True, 'message': '会话状态已重置'})
    except Exception as e:
        logging.error(f"[重置] 清除 checkpoint 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'error': f'重置失败: {str(e)}'}), 500

@agent_bp.route('/send_stream', methods=['POST'])
def handle_message_stream():
    """旧流式接口已下线，前端应使用 analysis job API。"""
    return jsonify({
        "success": False,
        "error": "旧 /api/send_stream 已废弃，请使用 analysis job API: POST /api/agent/jobs + GET /api/agent/jobs/<job_id>/events",
    }), 410


@agent_bp.route('/agent/jobs', methods=['POST'])
def create_analysis_job():
    """
    创建后台分析任务。

    Web 层只做认证、参数校验和 job 入队，不执行 Agent/MCP。
    同会话 active job 互斥由 job_service 和数据库唯一约束共同保证。
    """
    current_user = get_current_session_user()
    if not current_user:
        return jsonify({"success": False, "error": "用户未登录或会话已过期"}), 401

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    session_id = data.get("session_id")
    if not message:
        return jsonify({"success": False, "error": "消息不能为空"}), 400
    if not session_id:
        return jsonify({"success": False, "error": "请求无效，缺少会话ID"}), 400

    try:
        #  创建任务，获取任务是否创建成功表标识
        job, existing = job_service.create_job(current_user["id"], session_id, message)
        logging.info(
            "[job-api] user=%s session=%s job=%s existing=%s",
            current_user["id"],
            session_id,
            job["job_id"],
            existing,
        )
        return jsonify({
            "success": True,
            "job_id": job["job_id"],
            "status": job["status"],
            "existing": existing,
        }), 200 if existing else 202
    except PermissionError as exc:
        return jsonify({"success": False, "error": str(exc)}), 403
    except Exception as exc:
        logging.error("创建 analysis job 失败: %s", exc, exc_info=True)
        return jsonify({"success": False, "error": "创建任务失败"}), 500


@agent_bp.route('/agent/jobs/<job_id>/events')
def stream_analysis_job_events(job_id: str):
    """
    向前端推送指定 job 的 SSE 事件流。
    """
    current_user = get_current_session_user()
    if not current_user:
        return jsonify({"success": False, "error": "用户未登录或会话已过期"}), 401

    # 校验该会话属于当前用户，防止前端篡改
    job = job_service.get_job_for_user(job_id, current_user["id"])
    if not job:
        return jsonify({"success": False, "error": "任务不存在"}), 404

    last_event_id = request.headers.get("Last-Event-ID") or request.args.get("last_event_id") or "0"
    try:
        after_id = int(last_event_id)
    except ValueError:
        after_id = 0

    def generate():
        """轮询事件表并生成 SSE；终态事件出现后结束连接。"""
        # nonlocal是外部嵌套函数内的变量
        nonlocal after_id
        last_heartbeat = time.monotonic()
        ## 循环监听
        while True:
            events = job_service.read_events_after(job_id, after_id)
            for row in events:
                # 这里获取数据库中的id，并传给前端
                after_id = int(row["id"])
                ## payload事件具体包
                payload = row["payload_json"] or {}
                if isinstance(payload, dict) and "type" not in payload:
                    payload = {**payload, "type": row["event_type"]}
                yield _sse(row["event_type"], payload, after_id)
                if row["event_type"] in job_service.TERMINAL_EVENTS:
                    return

            current_job = job_service.get_job_for_user(job_id, current_user["id"])
            if current_job and current_job["status"] in job_service.TERMINAL_STATUSES:
                return
            ## 返回单调递增的时间戳
            now = time.monotonic()
            # 如果超过了心跳设置间隔，返回空包，保持连接
            if now - last_heartbeat >= settings.SSE_HEARTBEAT_INTERVAL_SECONDS:
                yield _sse("heartbeat", {"type": "heartbeat", "job_id": job_id})
                last_heartbeat = now
            time.sleep(settings.SSE_POLL_INTERVAL_SECONDS)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
