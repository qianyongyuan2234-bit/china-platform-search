"""小红书搜索 - 改用百度搜索小红书内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_xhs(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索小红书内容"""
    results = await search_baidu(client, keyword, limit, days_back=days_back, platform="xhs")
    return results
