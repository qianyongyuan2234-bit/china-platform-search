"""百度搜索 — httpx 快速路径 + 搜狗回退

不再依赖 Playwright（已废弃），被封锁时直接走搜狗回退。
纯标准库实现，无 bs4 依赖。
"""
from __future__ import annotations
import re
from datetime import datetime, timedelta, timezone
from models import SearchResult
from handlers.sogou import search_sogou
from utils.helpers import clean_html, unshorten_baidu_url

BASE = "https://m.baidu.com"
SEARCH_URL = f"{BASE}/s"

# 验证码/封锁检测关键字
_BLOCKED_PATTERNS = (
    "网络不给力",
    "请稍后重试",
    "安全验证",
    "验证码",
    "wappass.baidu.com",
    "captcha",
    "滑动验证",
    "百度安全验证",
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


def _is_blocked(body_text: str) -> bool:
    """检测百度是否返回了验证码/封锁页面"""
    return any(p in body_text for p in _BLOCKED_PATTERNS)


def _parse_baidu_results(html: str, limit: int, pname: str) -> list[SearchResult]:
    """从百度移动端搜索结果 HTML 中提取结果（正则，无 bs4）

    移动端百度结果结构：
      <div class="c-result"> 或 <div class="result">
        <h3 class="t"><a href="...">标题</a></h3>
        <div class="c-span-last">摘要</div>
      </div>
    """
    results = []
    seen_urls = set()

    # 定位所有结果块
    # 百度常用的结果块 class
    block_patterns = ['class="c-result"', 'class="result"', 'class="result-op"']

    positions = []
    for pat in block_patterns:
        if positions:
            break
        pos = 0
        while True:
            idx = html.find(pat, pos)
            if idx == -1:
                break
            positions.append(idx)
            pos = idx + 1

    if not positions:
        # 后备：直接找 h3 链接
        positions = [m.start() for m in re.finditer(r'<h3[^>]*class="t"', html)]
    if not positions:
        # 后备2：任意 h3
        positions = [m.start() for m in re.finditer(r'<h3[^>]*>', html)]

    for start_pos in positions:
        if len(results) >= limit:
            break

        # 取约 2000 字符作为一条结果块
        block = html[start_pos:start_pos + 2000]

        # 提取标题链接
        link_match = re.search(
            r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            block, re.DOTALL
        )
        if not link_match:
            continue

        href = link_match.group(1)
        title_html = link_match.group(2)
        title = clean_html(title_html)

        if not title or not href:
            continue

        # 跳过垃圾链接
        if href.startswith("#") or href == "javascript:;":
            continue

        if href in seen_urls:
            continue
        seen_urls.add(href)

        # 构建完整 URL
        if href.startswith("//"):
            full_url = "https:" + href
        elif href.startswith("/"):
            full_url = BASE + href
        else:
            full_url = href

        # 提取摘要
        content = ""
        for content_pat in (
            r'<div[^>]*class="c-span-last"[^>]*>(.*?)</div>',
            r'<div[^>]*class="c-abstract"[^>]*>(.*?)</div>',
            r'<span[^>]*class="content-right"[^>]*>(.*?)</span>',
            r'<p[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</p>',
        ):
            cm = re.search(content_pat, block, re.DOTALL)
            if cm:
                content = clean_html(cm.group(1))
                break

        # 判断内容类型
        content_type = "文字"
        # 后续让调用方根据 platform 覆盖

        results.append(SearchResult(
            title=title[:200],
            content=content[:500],
            url=full_url,
            platform=pname,
            content_type=content_type,
        ))

    return results


async def search_baidu(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
    platform: str | None = None,
) -> list[SearchResult]:
    """百度搜索（通用或指定站点）

    Args:
        client: HTTPClient 实例。
        keyword: 搜索关键词。
        limit: 返回结果数上限。
        days_back: 时间过滤（最近 N 天），None 表示不限。
        platform: 平台标识（在 SITE_MAP 中注册的 key），None 表示直接百度搜索。

    Returns:
        搜索结果列表，无结果时返回空列表。若百度被封锁，自动回退到搜狗搜索。
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

    # 时间过滤
    if days_back and days_back > 0:
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days_back)
        start_ts = int(start.timestamp())
        end_ts = int(now.timestamp())
        params["gpc"] = f"stf={start_ts},{end_ts}|stftype=1"

    try:
        resp = await client.get(SEARCH_URL, params=params, mobile=True)
        body_text = resp.text
    except Exception as e:
        print(f"  ❌ {name}: httpx 请求失败: {e}")
        print(f"  ⚠️ {name}: 回退到搜狗搜索…")
        return await search_sogou(client, keyword, limit, days_back, platform)

    # 检测封锁
    if _is_blocked(body_text):
        print(f"  ⚠️ {name}: 百度验证码封锁（可能需换 IP），回退到搜狗搜索…")
        # 传递原始平台标识，让搜狗 handler 做对应的 site: 查询
        return await search_sogou(client, keyword, limit, days_back, platform)

    # 纯标准库解析
    results = _parse_baidu_results(body_text, limit, name)

    if not results:
        print(f"  ℹ️ {name}: 页面内容解析无结果")
        # 可打开预览帮助调试
        preview = body_text[:200].replace("\n", " ")[:200]
        print(f"  🔍 页面预览: {preview}...")

    return results
