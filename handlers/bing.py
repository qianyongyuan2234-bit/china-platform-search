"""Bing CN 搜索 — 搜狗被封时的三级回退

Bing CN 的 site: 操作符对中国社交平台索引较浅，
因此采用通用搜索 + URL 域名过滤的方式模拟 site: 查询。

纯标准库实现，无 bs4 依赖。

回退链：百度 → 搜狗 → 必应 → DuckDuckGo（终点）
"""
from __future__ import annotations
import re
import random
import asyncio
from models import SearchResult
from handlers.ddg import search_ddg

SEARCH_URL = "https://cn.bing.com/search"

PLATFORM_DOMAINS = {
    "weibo": "weibo.com",
    "zhihu": "zhihu.com",
    "toutiao": "toutiao.com",
    "sohu": "sohu.com",
    "douyin": "douyin.com",
    "kuaishou": "kuaishou.com",
    "xhs": "xiaohongshu.com",
    "shipinhao": "channels.qq.com",
    "peoplerail": "peoplerail.com",
}

PLATFORM_NAMES = {
    "weibo": "微博",
    "zhihu": "知乎",
    "toutiao": "今日头条",
    "sohu": "搜狐",
    "douyin": "抖音",
    "kuaishou": "快手",
    "xhs": "小红书",
    "shipinhao": "视频号",
    "peoplerail": "人民铁道网",
}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _clean_title(title: str) -> str:
    """清理标题中混入的 URL/域名/面包屑残留"""
    # 去掉嵌入的完整 URL（如 "baidu.comhttps://baike.baidu.com"）
    title = re.sub(r'https?://[^\s]+', '', title)
    # 去掉 domain 前缀 + 面包屑分隔符（如 "baidu.com › "）
    title = re.sub(r'^[\w.-]+\.(?:com|cn|org|net)\s*[›>]\s*', '', title)
    # 合并多余空白
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def _parse_bing_results(html: str, limit: int, pname: str, domain: str | None) -> list[SearchResult]:
    """从 Bing CN 搜索结果 HTML 中提取结果"""
    results = []
    seen_urls = set()

    # Bing 的主要结果块：<li class="b_algo"> ... </li>
    # 定位所有 b_algo 块
    positions = []
    pos = 0
    while True:
        idx = html.find('class="b_algo"', pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 1

    for start_pos in positions:
        if len(results) >= limit:
            break

        block = html[start_pos:start_pos + 3000]

        # 提取链接和标题 — 优先从 <h2> 内提取，避免面包屑/attribution 链接干扰
        h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
        search_area = h2_match.group(1) if h2_match else block

        link_match = re.search(
            r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
            search_area, re.DOTALL
        )
        if not link_match:
            # <h2> 内未找到则回退到整个 block 中搜索
            link_match = re.search(
                r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                block, re.DOTALL
            )
        if not link_match:
            continue

        href = link_match.group(1)
        title_html = link_match.group(2)
        title = _clean_title(_strip_html(title_html))

        if not title or not href:
            continue
        if href in seen_urls:
            continue

        # 域名过滤（模拟 site:）
        if domain and domain not in href:
            continue

        seen_urls.add(href)

        # 提取摘要 — Bing 用 <p> 标签放摘要
        content = ""
        p_match = re.search(
            r'<p[^>]*>(.*?)</p>',
            block, re.DOTALL
        )
        if p_match:
            content = _strip_html(p_match.group(1))[:500]

        results.append(SearchResult(
            title=title[:200],
            content=content,
            url=href,
            platform=pname,
            content_type="文字",
        ))

    return results


async def search_bing(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
    platform: str | None = None,
) -> list[SearchResult]:
    """通过 Bing CN 搜索

    两级策略：
    1. 若有 platform：域名过滤（精确但覆盖率低）
    2. 若域名过滤无结果：回退到「关键词 + 平台名」宽松搜索

    Args:
        client: HTTPClient 实例
        keyword: 搜索关键词
        limit: 最大结果数
        days_back: 忽略（Bing 中文不支持可靠的时间过滤）
        platform: 平台标识，用于域名过滤

    Returns:
        搜索结果列表
    """
    domain = PLATFORM_DOMAINS.get(platform) if platform else None
    plat_name = PLATFORM_NAMES.get(platform, "")
    pname = plat_name or platform or "必应"

    # 小随机延迟，防并发限流
    await asyncio.sleep(random.uniform(0.3, 1.0))

    # ── 第一遍：域名过滤（精确匹配） ──
    if domain:
        query = "{} {}".format(keyword, domain)  # 不用 site:，用自然搜索
    else:
        query = keyword

    params = {"q": query}

    try:
        resp = await client.get(SEARCH_URL, params=params, headers={"Accept-Language": "zh-CN,zh;q=0.9"})
    except Exception as e:
        print(f"  ❌ 必应: {e}")
        print("  ⚠️ 回退到 DuckDuckGo…")
        return await search_ddg(client, keyword, limit, days_back, platform)

    html = resp.text

    if resp.status_code != 200 or len(html) < 500:
        print("  ⚠️ 必应响应异常，回退到 DuckDuckGo…")
        return await search_ddg(client, keyword, limit, days_back, platform)

    results = _parse_bing_results(html, limit, pname, domain)

    # ── 第二遍：域过滤无结果时，放宽到关键词匹配 ──
    if domain and not results and plat_name:
        fallback_query = "{} {}".format(keyword, plat_name)
        print(f"  ℹ️ 必应域过滤无结果，改用关键词: {fallback_query}")
        await asyncio.sleep(random.uniform(0.5, 1.0))
        try:
            resp2 = await client.get(SEARCH_URL, params={"q": fallback_query},
                                     headers={"Accept-Language": "zh-CN,zh;q=0.9"})
            if resp2.status_code == 200 and len(resp2.text) >= 500:
                results = _parse_bing_results(resp2.text, limit, pname, None)
        except Exception:
            pass

    if not results:
        preview = html[:200].replace("\n", " ")[:200]
        print(f"  ℹ️ 必应({pname}): 未解析到结果 页面预览: {preview}...")
        print("  ⚠️ 回退到 DuckDuckGo…")
        return await search_ddg(client, keyword, limit, days_back, platform)

    return results
