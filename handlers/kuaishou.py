"""快手搜索 - 改用百度搜索快手内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_kuaishou(client, keyword: str, limit: int = 10) -> list[SearchResult]:
    """通过百度搜索快手内容"""
    results = await search_baidu(client, f"site:kuaishou.com {keyword}", "kuaishou", limit)
    return results
