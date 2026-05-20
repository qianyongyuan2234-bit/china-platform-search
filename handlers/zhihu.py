"""知乎搜索 - 改用百度搜索知乎内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_zhihu(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索知乎内容"""
    results = await search_baidu(client, keyword, limit, days_back=days_back, platform="zhihu")
    return results
