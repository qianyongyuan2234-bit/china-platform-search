"""通用 HTTP 客户端工具"""
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


def get_headers(mobile: bool = False, **extra) -> dict:
    headers = {**HEADERS_BASE}
    if mobile:
        headers["User-Agent"] = random.choice([u for u in UA_LIST if "Mobile" in u or "iPhone" in u])
        headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    else:
        headers["User-Agent"] = random.choice([u for u in UA_LIST if "Mobile" not in u])
    headers.update(extra)
    return headers


class HTTPClient:
    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.session = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            verify=False,
        )

    async def get(self, url: str, mobile: bool = False, headers: dict | None = None, **kwargs) -> httpx.Response:
        h = get_headers(mobile=mobile)
        if headers:
            h.update(headers)
        return await self.session.get(url, headers=h, **kwargs)

    async def close(self):
        await self.session.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
