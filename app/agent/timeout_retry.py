"""
超时与重试工具模块

提供通用的超时控制和指数退避重试机制，供 LLM、MCP、RAG 等外部调用使用。
"""
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)

# 可重试的异常类型
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    TimeoutError,
    ConnectionError,
    ConnectionResetError,
    BrokenPipeError,
)


def _is_retryable(exc: Exception) -> bool:
    """判断异常是否值得重试"""
    if isinstance(exc, RETRYABLE_EXCEPTIONS):
        return True
    # OpenAI SDK 的 APIStatusError（5xx 可重试）
    try:
        from openai import APIStatusError
        if isinstance(exc, APIStatusError) and exc.status_code >= 500:
            return True
    except ImportError:
        pass
    # httpx 超时
    try:
        import httpx
        if isinstance(exc, httpx.TimeoutException):
            return True
    except ImportError:
        pass
    return False


"""
这个是同步函数
"""

def retry_on_failure(
    func: Callable,
    *args,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    """
    同步函数重试包装器（指数退避）。

    Args:
        func: 要执行的同步函数
        *args: 位置参数
        max_retries: 最大重试次数（不含首次调用）
        retry_delay: 首次重试等待秒数
        backoff_factor: 退避倍数
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次重试仍失败时抛出原异常
    """
    last_exc = None
    delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries and _is_retryable(e):
                logger.warning(
                    f"[重试] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                    f"{delay:.1f}s 后重试 (剩余 {max_retries - attempt} 次)"
                )
                time.sleep(delay)
                delay *= backoff_factor
            else:
                if attempt >= max_retries:
                    logger.error(
                        f"[重试] {func.__name__} 已达最大重试次数 ({max_retries})，放弃重试"
                    )
                raise

    raise last_exc


async def retry_on_failure_async(
    func: Callable,
    *args,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    """
    异步函数重试包装器（指数退避）。

    Args:
        func: 要执行的异步函数
        *args: 位置参数
        max_retries: 最大重试次数（不含首次调用）
        retry_delay: 首次重试等待秒数
        backoff_factor: 退避倍数
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Raises:
        最后一次重试仍失败时抛出原异常
    """
    last_exc = None
    delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            if attempt < max_retries and _is_retryable(e):
                logger.warning(
                    f"[重试] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                    f"{delay:.1f}s 后重试 (剩余 {max_retries - attempt} 次)"
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                if attempt >= max_retries:
                    logger.error(
                        f"[重试] {func.__name__} 已达最大重试次数 ({max_retries})，放弃重试"
                    )
                raise

    raise last_exc


async def call_with_timeout(coro, timeout: float) -> Any:
    """
    为协程添加超时控制。

    Args:
        coro: 要执行的协程
        timeout: 超时秒数

    Returns:
        协程返回值

    Raises:
        asyncio.TimeoutError: 超时时抛出
    """
    return await asyncio.wait_for(coro, timeout=timeout)


async def call_with_timeout_and_retry_async(
    func: Callable,
    *args,
    timeout: float = 120,
    max_retries: int = 2,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs
) -> Any:
    """
    异步函数：超时 + 重试组合包装器。

    每次调用都有独立的超时控制，失败后按指数退避重试。
    """
    last_exc = None
    delay = retry_delay

    for attempt in range(max_retries + 1):
        try:
            return await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=timeout
            )
        except Exception as e:
            last_exc = e
            if attempt < max_retries and _is_retryable(e):
                logger.warning(
                    f"[超时重试] {func.__name__} 第 {attempt + 1} 次失败: {e}，"
                    f"{delay:.1f}s 后重试 (剩余 {max_retries - attempt} 次)"
                )
                await asyncio.sleep(delay)
                delay *= backoff_factor
            else:
                if attempt >= max_retries:
                    logger.error(
                        f"[超时重试] {func.__name__} 已达最大重试次数 ({max_retries})，放弃重试"
                    )
                raise

    raise last_exc


def call_sync_with_timeout(func: Callable, *args, timeout: float = 120, **kwargs) -> Any:
    """
    在异步上下文中执行同步函数并添加超时。

    使用 ThreadPoolExecutor 在线程池中运行同步函数，
    再用 asyncio.wait_for 包装为可超时的协程。

    Args:
        func: 同步函数
        *args: 位置参数
        timeout: 超时秒数
        **kwargs: 关键字参数

    Returns:
        函数返回值
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = loop.run_in_executor(pool, lambda: func(*args, **kwargs))
        return asyncio.wait_for(future, timeout=timeout)
