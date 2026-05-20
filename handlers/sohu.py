"""搜狐新闻搜索"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
from models import SearchResult

SEARCH_URL = "https://www.sogou.com/web"


async def search_sohu(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    results = []
    # 通过搜狗搜索搜狐站点
    params = {
        "query": f"site:sohu.com {keyword}",
        "ie": "utf8",
    }
    resp = await client.get(SEARCH_URL, params=params)
    soup = BeautifulSoup(resp.text, "html.parser")

    for item in soup.select("div.vrwrap, div.rb, div.results"):
        if len(results) >= limit:
            break
        result = _parse_sogou_sohu_item(item, "搜狐")
        if result:
            results.append(result)

    # 如果搜狐结果不够，也搜一下搜狐新闻
    if len(results) < limit:
        params["query"] = f"site:news.sohu.com {keyword}"
        resp2 = await client.get(SEARCH_URL, params=params)
        soup2 = BeautifulSoup(resp2.text, "html.parser")
        for item in soup2.select("div.vrwrap, div.rb, div.results"):
            if len(results) >= limit:
                break
            result = _parse_sogou_sohu_item(item, "搜狐新闻")
            if result and result.url not in [r.url for r in results]:
                results.append(result)

    return results


def _parse_sogou_sohu_item(item, platform_name: str) -> SearchResult | None:
    title_el = item.select_one("h3 a")
    if not title_el:
        return None

    title = title_el.get_text(strip=True)
    url = title_el.get("href", "")
    if not url:
        return None

    content_el = item.select_one("div.txt-info p, p")
    content = content_el.get_text(strip=True) if content_el else ""

    # 摘要中去除关键词高亮标签
    content = re.sub(r"<[^>]+>", "", content)

    return SearchResult(
        title=title[:200],
        content=content[:500],
        url=url,
        platform=platform_name,
        content_type="文字",
    )
