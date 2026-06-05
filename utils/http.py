"""通用 HTTP 客户端工具 — 自动重试、UA 随机池"""
from __future__ import annotations
import asyncio
import httpx
import random

UA_LIST = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# 可重试的异常类型
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.TimeoutException,
    httpx.RemoteProtocolError,
)

# 可重试的 HTTP 状态码
_RETRYABLE_STATUSES = {500, 502, 503, 504}

# 重试配置
_MAX_RETRIES = 2
_RETRY_BACKOFF_BASE = 1.0  # 秒，指数退避基数


def get_headers(mobile: bool = False, **extra) -> dict:
    """获取随机 UA 请求头"""
    headers = {**HEADERS_BASE}
    if mobile:
        headers["User-Agent"] = random.choice([u for u in UA_LIST if "Mobile" in u or "iPhone" in u])
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    else:
        headers["User-Agent"] = random.choice([u for u in UA_LIST if "Mobile" not in u])
    headers.update(extra)
    return headers


def _should_retry(response: httpx.Response | None, exception: Exception | None) -> bool:
    """判断是否应该重试"""
    if exception is not None:
        return isinstance(exception, _RETRYABLE_EXCEPTIONS)
    if response is not None:
        return response.status_code in _RETRYABLE_STATUSES
    return False


class HTTPClient:
    """HTTP 客户端，封装 httpx.AsyncClient，支持自动重试和 UA 随机池。

    Attributes:
        session: 内部的 httpx.AsyncClient 实例。

    Usage:
        async with HTTPClient() as client:
            resp = await client.get("https://example.com")
    """

    def __init__(self, timeout: float = 15.0):
        """初始化 HTTP 客户端。

        Args:
            timeout: 请求超时时间（秒），同时用于 connect/read/write。
                     默认 15s，内部转换为 httpx.Timeout(connect=10, read=20, pool=5)。
        """
        # 使用结构化 timeout，给连接和读取独立的上限
        self.timeout = httpx.Timeout(
            timeout=30.0,       # 总超时 30s
            connect=10.0,       # 连接超时 10s
            read=20.0,          # 读取超时 20s
            write=10.0,         # 写入超时 10s
            pool=5.0,           # 连接池超时 5s
        )
        self.session = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            verify=False,
        )

    async def get(
        self,
        url: str,
        mobile: bool = False,
        headers: dict | None = None,
        **kwargs,
    ) -> httpx.Response:
        """发送 GET 请求，自动重试连接失败/超时/5xx。

        Args:
            url: 请求 URL。
            mobile: 是否使用移动端 User-Agent。
            headers: 额外的请求头。
            **kwargs: 透传给 httpx.AsyncClient.get()。

        Returns:
            httpx.Response 对象。

        Raises:
            httpx.HTTPError: 重试耗尽后仍失败。
        """
        h = get_headers(mobile=mobile)
        if headers:
            h.update(headers)

        last_exception: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):  # 0, 1, 2 → 共 3 次尝试
            try:
                response = await self.session.get(url, headers=h, **kwargs)
                if response.status_code not in _RETRYABLE_STATUSES:
                    return response
                # 5xx → 准备重试
                last_exception = None
            except _RETRYABLE_EXCEPTIONS as e:
                response = None
                last_exception = e

            # 还有重试机会则退避后重试
            if attempt < _MAX_RETRIES:
                delay = _RETRY_BACKOFF_BASE * (2 ** attempt)  # 1s, 2s
                print(f"  ⚠️ HTTP 请求失败 (第 {attempt + 1} 次)，{delay:.0f}s 后重试: {url[:60]}")
                await asyncio.sleep(delay)

        # 重试耗尽
        if last_exception:
            raise last_exception
        return response  # 最后一次是 5xx，返回该响应（调用方自行处理状态码）

    async def close(self):
        """关闭 HTTP 客户端会话"""
        await self.session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
