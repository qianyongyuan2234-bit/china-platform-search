"""微博搜索 - 改用百度搜索微博内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_weibo(client, keyword: str, limit: int = 10) -> list[SearchResult]:
    """通过百度搜索微博内容"""
    results = await search_baidu(client, f"site:weibo.com {keyword}", "weibo", limit)
    return results
