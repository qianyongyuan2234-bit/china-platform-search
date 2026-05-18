"""今日头条搜索 - 改用百度搜索头条内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_toutiao(client, keyword: str, limit: int = 10) -> list[SearchResult]:
    """通过百度搜索头条内容"""
    # 使用 site: 搜索限制在头条域名
    results = await search_baidu(client, f"site:toutiao.com {keyword}", "toutiao", limit)
    return results
