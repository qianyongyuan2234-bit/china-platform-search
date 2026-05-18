"""知乎搜索 - 改用百度搜索知乎内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_zhihu(client, keyword: str, limit: int = 10) -> list[SearchResult]:
    """通过百度搜索知乎内容"""
    results = await search_baidu(client, f"site:zhihu.com {keyword}", "zhihu", limit)
    return results
