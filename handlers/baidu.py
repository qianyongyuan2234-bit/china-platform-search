"""百度搜索"""
import re
from bs4 import BeautifulSoup
from models import SearchResult
from utils.helpers import clean_html, unshorten_baidu_url

BASE = "https://www.baidu.com"
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
    "douyin": ("抖音", "site:v.douyin.com"),
    "kuaishou": ("快手", "site:www.kuaishou.com"),
    "xhs": ("小红书", "site:xiaohongshu.com"),
    "shipinhao": ("视频号", "site:channels.qq.com"),
}


async def search_baidu(client, keyword: str, platform: str, limit: int = 10) -> list[SearchResult]:
    """百度搜索（通用或指定站点）"""
    results = []

    if platform in SITE_MAP:
        name, site_query = SITE_MAP[platform]
        query = f"{site_query} {keyword}"
    else:
        name = "百度"
        query = keyword

    params = {
        "wd": query,
        "rn": str(limit),
        "ie": "utf-8",
    }

    resp = await client.get(SEARCH_URL, params=params, mobile=False)
    soup = BeautifulSoup(resp.text, "html.parser")

    # 百度新布局使用 ol -> div.result
    for result_div in soup.select("div.result, div.c-container, .data-item"):
        if len(results) >= limit:
            break
        result = await _parse_baidu_item(client, result_div, keyword, name, platform)
        if result:
            results.append(result)

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
