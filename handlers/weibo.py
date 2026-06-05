"""微博搜索 - 改用百度搜索微博内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_weibo(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索微博内容"""
    try:
        results = await search_baidu(client, keyword, limit, days_back=days_back, platform="weibo")
        return results
    except Exception as e:
        print(f"  ❌ 微博: {e}")
        return []
