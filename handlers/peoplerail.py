"""人民铁道网搜索 — 直接爬取 peoplerail.com 站内搜索接口

站内搜索接口：
  https://www.peoplerail.com/index.php?m=search&c=index&a=init&typeid=56&siteid=1&q={关键词}
  返回 HTML 页面，纯标准库正则解析，无 bs4 依赖。
"""
from __future__ import annotations
import re
from urllib.parse import quote
from models import SearchResult

# 站内搜索接口 URL 模板
_SEARCH_URL = "https://www.peoplerail.com/index.php"
_SEARCH_PARAMS_TEMPLATE = {
    "m": "search",
    "c": "index",
    "a": "init",
    "typeid": "56",
    "siteid": "1",
}

# 文章链接格式：/rail/show-XXXX-XXXXXX-1.html
_ARTICLE_HREF_RE = re.compile(
    r'<a\s+[^>]*href="(https?://(?:www\.)?peoplerail\.com/rail/show-[^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)

# 需要排除的链接关键字
_EXCLUDE_PATTERNS = (
    "special/index",    # 专题页
)


def _strip_html(text: str) -> str:
    """去除 HTML 标签并清理空白"""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_search_results(html: str, limit: int) -> list[SearchResult]:
    """从人民铁道网站内搜索结果 HTML 中提取结果

    搜索结果页面中的文章链接格式：
      <a href="http://www.peoplerail.com/rail/show-XXXX-XXXXXX-1.html" target="_blank">标题</a>

    过滤规则：
      - 只保留 peoplerail.com 域名下的链接
      - 排除专题页（special/index 等）

    Args:
        html: 搜索结果页 HTML 文本
        limit: 最大返回结果数

    Returns:
        解析出的 SearchResult 列表
    """
    results: list[SearchResult] = []
    seen_urls: set[str] = set()

    for match in _ARTICLE_HREF_RE.finditer(html):
        if len(results) >= limit:
            break

        href = match.group(1)
        title_html = match.group(2)
        title = _strip_html(title_html)

        # 跳过空标题/空链接
        if not title or not href:
            continue

        # 排除非 peoplerail.com 域名（如 people.com.cn）
        if "peoplerail.com" not in href:
            continue

        # 排除专题页等非文章页面
        if any(pat in href for pat in _EXCLUDE_PATTERNS):
            continue

        # 去重
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # 截断标题到合理长度
        title = title[:200]

        results.append(SearchResult(
            title=title,
            url=href,
            platform="人民铁道网",
            content_type="文字",
        ))

    return results


async def search_peoplerail(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
) -> list[SearchResult]:
    """搜索人民铁道网内容

    直接调用 peoplerail.com 站内搜索接口，非百度 site: 代理。
    站内搜索接口不支持时间过滤，days_back 参数会被忽略。

    Args:
        client: HTTPClient 实例
        keyword: 搜索关键词
        limit: 最大返回结果数
        days_back: 忽略（站内搜索不支持时间过滤）

    Returns:
        搜索结果列表，网络不通或解析失败时返回空列表
    """
    # 构造查询参数
    params = {**_SEARCH_PARAMS_TEMPLATE, "q": keyword}

    try:
        resp = await client.get(_SEARCH_URL, params=params)
    except Exception as e:
        print(f"  ⚠️ 人民铁道网: 请求失败 ({e})")
        return []

    html = resp.text

    # 检查响应是否正常
    if resp.status_code != 200 or len(html) < 200:
        print(f"  ⚠️ 人民铁道网: 响应异常 (status={resp.status_code}, len={len(html)})")
        return []

    results = _parse_search_results(html, limit)

    if not results:
        preview = html[:300].replace("\n", " ")[:300]
        print(f"  ℹ️ 人民铁道网: 未解析到结果 页面预览: {preview}...")

    return results
