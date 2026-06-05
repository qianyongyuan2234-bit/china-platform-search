"""视频号搜索 - 改百度搜索视频号内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_shipinhao(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索视频号内容"""
    try:
        results = await search_baidu(client, keyword, limit, days_back=days_back, platform="shipinhao")
        return results
    except Exception as e:
        print(f"  ❌ 视频号: {e}")
        return []
