"""百度搜索"""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from models import SearchResult
from utils.helpers import clean_html, unshorten_baidu_url

BASE = "https://m.baidu.com"
SEARCH_URL = f"{BASE}/s"

# 标题区 / 结构化结果中的链接选择器（按优先级）
_HREF_SELECTORS = (
    "h3.t a[href]",
    "h3 a[href]",
    ".t a[href]",
    ".c-title a[href]",
    ".title a[href]",
    "a.c-font-medium[href]",
    "a[data-click][href]",
    "a[href]",
)

SITE_MAP = {
    "weibo": ("微博", "site:weibo.com"),
    "toutiao": ("今日头条", "site:toutiao.com"),
    "zhihu": ("知乎", "site:zhihu.com"),
    "douyin": ("抖音", "site:douyin.com"),
    "kuaishou": ("快手", "site:www.kuaishou.com"),
    "xhs": ("小红书", "site:xiaohongshu.com"),
    "shipinhao": ("视频号", "site:channels.qq.com"),
    "peoplerail": ("人民铁道网", "site:peoplerail.com"),
}


async def search_baidu(client, keyword: str, limit: int = 10, days_back: int | None = None, platform: str | None = None) -> list[SearchResult]:
    """百度搜索（通用或指定站点）

    Args:
        client: HTTPClient 实例。
        keyword: 搜索关键词。
        limit: 返回结果数上限。
        days_back: 时间过滤（最近 N 天），None 表示不限。
        platform: 平台标识（在 SITE_MAP 中注册的 key），None 表示直接百度搜索。

    Returns:
        搜索结果列表，无结果时返回空列表。
    """
    results = []

    if platform and platform in SITE_MAP:
        name, site_query = SITE_MAP[platform]
        query = f"{site_query} {keyword}"
    else:
        name = "百度"
        query = keyword

    params = {
        "word": query,
        "rn": str(limit),
        "ie": "utf-8",
    }

    # 时间过滤：百度 gpc 参数 (最近 N 天)
    if days_back and days_back > 0:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days_back)
        start_ts = int(start.timestamp())
        end_ts = int(now.timestamp())
        params["gpc"] = f"stf={start_ts},{end_ts}|stftype=1"

    resp = await client.get(SEARCH_URL, params=params, mobile=True)
    soup = BeautifulSoup(resp.text, "html.parser")

    # 移动端百度结果结构
    result_blocks = soup.select("div.c-result, div.result, .result-item, div.c-container")

    # 诊断：无结果块 → 页面结构可能已变化
    if not result_blocks:
        print(f"  ⚠️ {name}: 选择器未匹配到任何结果块（页面结构可能已变化，需更新 CSS 选择器）")
        # 尝试输出页面片段辅助排查（仅 verbose 场景输出前 500 字符）
        body = soup.body
        if body:
            preview = body.get_text(strip=True)[:300]
            print(f"  🔍 页面预览: {preview}...")
        return results

    for result_div in result_blocks:
        if len(results) >= limit:
            break
        try:
            result = await _parse_baidu_item(client, result_div, keyword, name, platform)
            if result:
                results.append(result)
        except Exception as e:
            # 单条解析失败不影响其他条
            print(f"  ⚠️ {name}: 解析单条结果失败: {e}")
            continue

    # 诊断：有结果块但全部解析失败 → 链接选择器可能失效
    if not results:
        print(f"  ℹ️ {name}: 匹配到 {len(result_blocks)} 个结果块但均未提取到有效链接"
              f"（可能是页面无搜索结果，或内部链接选择器失效）")

    return results


def _extract_href_from_block(item) -> str:
    """从一条结果块中提取最可信的跳转 href。"""
    for sel in _HREF_SELECTORS:
        el = item.select_one(sel)
        if el and el.get("href"):
            h = el["href"].strip()
            if h and not h.startswith("#") and h != "javascript:;":
                return h
    # 部分模板把地址放在 mu / data-url
    for attr in ("mu", "data-url", "data-href"):
        holder = item.select_one(f"[{attr}]")
        if holder and holder.get(attr):
            m = re.search(r"https?://[^\s'\"<>]+", holder[attr])
            if m:
                return m.group(0)
    return ""


def _title_element_for_block(item):
    return item.select_one("h3 a, h3 .t a, h3, .c-title a, .title a, .t a")


async def _parse_baidu_item(
    client, item, keyword: str, platform_name: str, platform: str
) -> SearchResult | None:
    title_el = _title_element_for_block(item)
    if not title_el:
        return None

    href = ""
    if title_el.name == "a" and title_el.get("href"):
        href = title_el["href"].strip()
    else:
        inner_a = title_el.find("a", href=True) or title_el.find_parent("a", href=True)
        if inner_a and inner_a.get("href"):
            href = inner_a["href"].strip()
    if not href:
        href = _extract_href_from_block(item)
    if not href:
        return None

    url = await unshorten_baidu_url(client, href, referer=SEARCH_URL)
    if not url.startswith("http"):
        if href.startswith("//"):
            url = "https:" + href
        elif href.startswith("/"):
            url = BASE + href

    if not url:
        return None

    title_html = title_el.get_text(strip=True)
    title = clean_html(title_html)
    if not title:
        return None

    # 摘要
    content_el = item.select_one(".content, .content_1, .c-span-last, .f14tj, .result-content, p, .content-right")
    content = clean_html(content_el.get_text(strip=True)) if content_el else ""

    # 判断内容类型
    content_type = "文字"
    if platform in ("douyin", "kuaishou", "shipinhao"):
        content_type = "视频"
    elif platform == "xhs":
        content_type = "图文"
    elif any(ext in url for ext in [".mp4", "video"]):
        content_type = "视频"

    return SearchResult(
        title=title[:200],
        content=content[:500],
        url=url,
        platform=platform_name,
        content_type=content_type,
    )
