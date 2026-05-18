"""通用工具函数"""
import re
import urllib.parse
from urllib.parse import parse_qs, unquote, urlparse

BAIDU_BASE = "https://www.baidu.com"


def clean_html(text: str) -> str:
    """去除 HTML 标签"""
    return re.sub(r"<[^>]+>", "", text) if text else ""


def _normalize_href(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BAIDU_BASE + href
    return href


def _decode_url_query_param(link: str) -> str | None:
    """若 link 的 query 里直接带有可解码的真实 http(s) URL，则返回之。"""
    if "url=" not in link:
        return None
    try:
        q = parse_qs(urlparse(link).query)
        raw = (q.get("url") or [None])[0]
        if not raw:
            return None
        decoded = unquote(raw)
        if decoded.startswith("http://") or decoded.startswith("https://"):
            return decoded
    except Exception:
        pass
    return None


def _is_baidu_jump(href: str) -> bool:
    if not href:
        return False
    low = href.lower()
    return "baidu.com/link" in low or "/link?" in low or low.startswith("http://www.baidu.com/link")


async def unshorten_baidu_url(client, href: str, *, referer: str | None = None) -> str:
    """
    解析百度跳转 / 中间页，尽量得到最终落地 URL。
    多数 /link?url= 后的参数是加密串，仅靠解码拿不到真实地址，需跟随重定向。
    """
    href = _normalize_href(href)
    if not href:
        return href

    plain = _decode_url_query_param(href)
    if plain and not _is_baidu_jump(plain):
        return plain

    m = re.search(r"(https?://[^\s&'\"<>]+)", href)
    if m and not _is_baidu_jump(m.group(1)):
        return m.group(1)

    if _is_baidu_jump(href):
        headers = {}
        if referer:
            headers["Referer"] = referer
        try:
            resp = await client.get(href, headers=headers or None, follow_redirects=True)
            final = str(resp.url).split("#")[0]
            if final and (not _is_baidu_jump(final) or final != href):
                return final
        except Exception:
            pass

    return href
