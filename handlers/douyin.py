"""抖音搜索 - 改用百度搜索抖音内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_douyin(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索抖音内容"""
    try:
        results = await search_baidu(client, keyword, limit, days_back=days_back, platform="douyin")
        return results
    except Exception as e:
        print(f"  ❌ 抖音: {e}")
        return []
