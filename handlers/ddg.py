"""DuckDuckGo 搜索 — 四级回退终点

使用 DuckDuckGo HTML 版（无 JS 依赖），纯标准库正则解析。
网络不通时优雅返回空列表，不抛异常。

⚠️ 此 handler 是回退链终点，绝不回调上游（bing/sogou/baidu），避免无限递归。
"""
from __future__ import annotations
import re
import random
import asyncio
from models import SearchResult

SEARCH_URL = "https://html.duckduckgo.com/html/"

# 平台域名映射（用于 domain 过滤）
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
    """去除 HTML 标签"""
    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_ddg_results(html: str, limit: int, pname: str, domain: str | None) -> list[SearchResult]:
    """从 DuckDuckGo HTML 搜索结果中提取结果

    DDG HTML 版结果结构：
      <div class="result results_links results_links_deep">
        <h2 class="result__title">
          <a class="result__a" href="...">标题</a>
        </h2>
        <div class="result__extract">
          <a class="result__snippet">摘要</a>
        </div>
      </div>
    """
    results = []
    seen_urls = set()

    # 匹配所有 result__a 链接
    for match in re.finditer(
        r'<a[^>]*class="[^"]*result__a[^"]*"[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
        html, re.DOTALL
    ):
        if len(results) >= limit:
            break

        href = match.group(1)
        title_html = match.group(2)
        title = _strip_html(title_html)

        if not title or not href:
            continue
        if href in seen_urls:
            continue

        # 域名过滤（模拟 site: 查询）
        if domain and domain not in href:
            continue

        seen_urls.add(href)

        # 在当前链接附近找摘要（snippet 在链接后面不远处）
        content = ""
        context_end = min(len(html), match.end() + 1000)
        context = html[match.end():context_end]

        snippet_match = re.search(
            r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</(?:a|span|div|p)>',
            context, re.DOTALL
        )
        if snippet_match:
            content = _strip_html(snippet_match.group(1))[:500]

        results.append(SearchResult(
            title=title[:200],
            content=content,
            url=href,
            platform=pname,
            content_type="文字",
        ))

    return results


async def search_ddg(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
    platform: str | None = None,
) -> list[SearchResult]:
    """通过 DuckDuckGo HTML 搜索

    直接搜索 DDG 全站，非 site: 代理。

    Args:
        client: HTTPClient 实例
        keyword: 搜索关键词
        limit: 最大结果数
        days_back: 忽略（DDG 不支持可靠的时间过滤）
        platform: 平台标识，用于域名过滤

    Returns:
        搜索结果列表，网络不通时返回空列表
    """
    domain = PLATFORM_DOMAINS.get(platform) if platform else None
    plat_name = PLATFORM_NAMES.get(platform, "")
    pname = plat_name or platform or "DuckDuckGo"

    # 小随机延迟，防并发限流
    await asyncio.sleep(random.uniform(0.3, 0.8))

    # 构造查询词：有 platform 时附加中文平台名（DDG 对中文 site: 语法支持差）
    if plat_name:
        query = "{} {}".format(keyword, plat_name)
    else:
        query = keyword

    params = {"q": query}

    try:
        resp = await client.get(SEARCH_URL, params=params,
                                headers={"Accept-Language": "zh-CN,zh;q=0.9"})
    except Exception as e:
        print(f"  ⚠️ DuckDuckGo: 请求失败 ({e})")
        return []

    html = resp.text

    if resp.status_code != 200 or len(html) < 200:
        print("  ⚠️ DuckDuckGo: 响应异常")
        return []

    results = _parse_ddg_results(html, limit, pname, domain)

    if not results:
        preview = html[:200].replace("\n", " ")[:200]
        print(f"  ℹ️ DuckDuckGo({pname}): 未解析到结果 页面预览: {preview}...")

    return results
