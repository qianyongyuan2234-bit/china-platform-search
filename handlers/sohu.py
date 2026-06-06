"""搜狐新闻搜索 — 委托给搜狗 handler（site:sohu.com）"""
from __future__ import annotations
from handlers.sogou import search_sogou
from models import SearchResult


async def search_sohu(
    client,
    keyword: str,
    limit: int = 10,
    days_back: int | None = None,
) -> list[SearchResult]:
    """通过搜狗搜索查询搜狐内容

    委托给 search_sogou(client, keyword, limit, days_back, platform='sohu')。
    """
    results = await search_sogou(client, keyword, limit, days_back, platform="sohu")
    # 搜狗回的可能只有 site:sohu.com 结果，
    # 如果不够，再补 site:news.sohu.com 去重
    if len(results) < limit:
        more = await search_sogou(client, keyword, limit - len(results), days_back, platform=None)
        # platform=None 时搜狗直接搜索全站，从中筛选搜狐新闻
        news_results = [r for r in more if ("sohu.com" in r.url and r.url not in {x.url for x in results})]
        results.extend(news_results[:limit - len(results)])
    return results
