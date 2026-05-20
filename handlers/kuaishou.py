"""快手搜索 - 改用百度搜索快手内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_kuaishou(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索快手内容"""
    results = await search_baidu(client, keyword, limit, days_back=days_back, platform="kuaishou")
    return results
