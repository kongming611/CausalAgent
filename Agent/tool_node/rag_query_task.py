"""
@task封装的RAG查询任务
"""
import logging
import asyncio
from typing import Dict, List, Union

from langgraph.func import task

from Agent.knowledge_base.query_rag import get_rag_response
from config.settings import settings
from app.agent.timeout_retry import retry_on_failure


@task
def rag_query_task(questions: List[Union[str, Dict]]) -> Dict:
    """
    Task: 查询知识库（RAG）

    Args:
        questions: 要查询的问题列表，支持字符串问题和结构化问题对象。

    Returns:
        dict: 结构化的知识库查询结果。
    """
    logging.info("正在启动RAG查询任务...")
    try:
        # 使用线程池包装同步调用并添加超时
        loop = asyncio.get_event_loop()
        rag_response = retry_on_failure(
            get_rag_response, questions,
            max_retries=settings.RAG_MAX_RETRIES
        )
        logging.info("Task: 知识库查询完成")
        return rag_response

    except Exception as exc:
        logging.error(f"Task: 知识库查询失败: {exc}", exc_info=True)
        return {
            "success": False,
            "summary": f"知识库查询失败：{exc}",
            "questions": [],
            "evidence_count": 0,
            "error": str(exc),
        }
