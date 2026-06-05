"""人民铁道网搜索 - 改用百度搜索人民铁道网内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_peoplerail(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索人民铁道网内容 (site:peoplerail.com)"""
    try:
        results = await search_baidu(client, keyword, limit, days_back=days_back, platform="peoplerail")
        return results
    except Exception as e:
        print(f"  ❌ 人民铁道网: {e}")
        return []
