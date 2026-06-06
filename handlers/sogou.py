"""搜狗通用搜索 — 替代 Baidu site: 查询的后备引擎

支持通过搜狗搜索 (sogou.com/web) 进行 site: 查询，
覆盖百度被封后的所有平台搜索。

纯标准库实现，无 bs4 依赖。
"""
from __future__ import annotations
import re
import random
import asyncio
from models import SearchResult
from handlers.bing import search_bing

# 串行锁：搜狗对并发极其敏感，同一时刻只允许一个请求
_sogou_lock = asyncio.Lock()

SEARCH_URL = "https://www.sogou.com/web"

# 平台 -> 搜狗 site: 域名映射
PLATFORM_SITES = {
    "weibo": "weibo.com",
    "zhihu": "zhihu.com",
    "toutiao": "toutiao.com",
    "sohu": "sohu.com",        # 主域
    "douyin": "douyin.com",
    "kuaishou": "kuaishou.com",
    "xhs": "xiaohongshu.com",
    "shipinhao": "weixin.qq.com",   # 视频号在微信域名下
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


def _parse_sogou_results(html: str, limit: int, pname: str) -> list[SearchResult]:
    """从搜狗搜索结果 HTML 中提取结果列表（纯正则，无 bs4/lxml）

    搜狗结果页结构（需适配的要点）：
      - 每个结果块: <div class="vrwrap">...</div>
      - 标题链接: <h3 class="vr-title"><a href="/link?url=..." class=" ">标题</a></h3>
      - 摘要/简介: <p class="str_info">... 或 div.text-layout 下的 p 标签
      - 标题中可能有 <em><!--red_beg-->keyword<!--red_end--></em> 高亮标签
    """
    # 第一步：提取所有 vrwrap 结果块
    # 用简单的 div class 定位，取到下一个 div.close 或平行边界
    results = []

    # 从 HTML 中定位所有 vrwrap 块
    # 搜狗的 vrwrap 块是自闭合结构：<div class="vrwrap"> ... </div></div></div>
    # 但不确定有几层闭合，改用更稳健的策略：找到每个 vrwrap 的开头，
    # 然后解析到下一个 <div class="vrwrap"（同级块）或 </div>\s*</div>\s*</div>$ 模式

    # 策略：找 h3 > a 链接，每个链接就是一条结果
    # 链接模式：<h3[^>]*>.*?<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>
    # 提取之后，再往后面找摘要

    # 先定位到所有 vrwrap 容器
    positions = []
    pos = 0
    while True:
        idx = html.find('class="vrwrap"', pos)
        if idx == -1:
            # Try alternative: class="rb" (Sogou may use different classes)
            idx = html.find('class="rb"', pos)
            if idx == -1:
                break
        positions.append(idx)
        pos = idx + 1  # scan forward

    if not positions:
        # Fallback: try to find h3 links anywhere (for mobile/alternate layouts)
        positions = _find_h3_positions(html)

    # 从每个容器中提取链接和摘要
    seen_urls = set()
    for start_pos in positions:
        if len(results) >= limit:
            break

        # 从 start_pos 取出约 2000 字符作为结果块
        block = html[start_pos:start_pos + 2500]

        # 提取标题链接
        link_match = re.search(
            r'<a[^>]*href="(/link\?url=[^"]*)"[^>]*>(.*?)</a>',
            block, re.DOTALL
        )
        if not link_match:
            # Try longer href format
            link_match = re.search(
                r'<a[^>]*href="(https?://[^"]*)"[^>]*>(.*?)</a>',
                block, re.DOTALL
            )
        if not link_match:
            continue

        href = link_match.group(1)
        title_html = link_match.group(2)
        title = _strip_html(title_html)

        if not title:
            continue

        # 去重
        if href in seen_urls:
            continue
        seen_urls.add(href)

        # 构建完整 URL（搜狗用相对路径）
        if href.startswith("/"):
            full_url = "https://www.sogou.com" + href
        else:
            full_url = href

        # 提取摘要
        # 尝试几种可能的摘要容器
        content = ""

        # 1. <p class="str_info">...</p>
        content_match = re.search(
            r'<p\s+class="str_info"[^>]*>(.*?)</p>',
            block, re.DOTALL
        )
        if content_match:
            content = _strip_html(content_match.group(1))
        else:
            # 2. div.text-layout 下的 p 标签
            text_layout_match = re.search(
                r'<div\s+class="text-layout"[^>]*>(.*?)</div>',
                block, re.DOTALL
            )
            if text_layout_match:
                text_block = text_layout_match.group(1)
                p_match = re.search(r'<p[^>]*>(.*?)</p>', text_block, re.DOTALL)
                if p_match:
                    content = _strip_html(p_match.group(1))

            if not content:
                # 3. 随便找个 p 标签
                p_match = re.search(
                    r'<p[^>]*>\s*(.{20,}?)\s*</p>',
                    block, re.DOTALL
                )
                if p_match:
                    content = _strip_html(p_match.group(1))[:300]

        results.append(SearchResult(
            title=title[:200],
            content=content[:500],
            url=full_url,
            platform=pname,
            content_type="文字",
        ))

    return results


def _find_h3_positions(html: str) -> list[int]:
    """后备：通过 h3 链接定位结果"""
    positions = []
    for m in re.finditer(r'class="vr-title', html):
        positions.append(m.start())
    if not positions:
        for m in re.finditer(r'<h3[^>]*>', html):
            positions.append(m.start())
    return positions


async def search_sogou(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
    platform: str | None = None,
) -> list[SearchResult]:
    """通过搜狗搜索执行 site: 查询

    Args:
        client: HTTPClient 实例
        keyword: 搜索关键词
        limit: 最大结果数
        days_back: 已忽略（搜狗不支持日期过滤）
        platform: 平台标识（weibo/zhihu/sohu/...），为 None 则搜全站

    Returns:
        搜索结果列表
    """
    site = PLATFORM_SITES.get(platform) if platform else None
    pname = PLATFORM_NAMES.get(platform, platform or "搜狗")

    if site:
        query = "site:{} {}".format(site, keyword)
    else:
        query = keyword

    params = {"query": query, "ie": "utf8"}

    # 串行化搜狗请求：并发必触发反爬
    async with _sogou_lock:
        await asyncio.sleep(random.uniform(0.3, 0.8))

        try:
            resp = await client.get(SEARCH_URL, params=params)
        except Exception as e:
            print("  ❌ 搜狗: {}".format(e))
            print("  ⚠️ 回退到必应搜索…")
            return await search_bing(client, keyword, limit, days_back, platform)

        html = resp.text

    # 检测验证码/反爬
    if "antispider" in html or "安全验证" in html:
        print("  ⚠️ 搜狗反爬，回退到必应搜索…")
        return await search_bing(client, keyword, limit, days_back, platform)

    results = _parse_sogou_results(html, limit, pname)
    if not results:
        print("  ⚠️ 搜狗无结果，回退到必应搜索…")
        return await search_bing(client, keyword, limit, days_back, platform)
    return results
