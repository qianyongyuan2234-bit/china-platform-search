"""今日头条搜索 - 改用百度搜索头条内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_toutiao(client, keyword: str, limit: int = 10, days_back: int = None) -> list[SearchResult]:
    """通过百度搜索头条内容"""
    # 使用 site: 搜索限制在头条域名
    try:
        results = await search_baidu(client, keyword, limit, days_back=days_back, platform="toutiao")
        return results
    except Exception as e:
        print(f"  ❌ 今日头条: {e}")
        return []
