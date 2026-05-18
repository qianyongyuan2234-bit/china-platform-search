"""视频号搜索 - 改百度搜索视频号内容"""
from models import SearchResult
from handlers.baidu import search_baidu

async def search_shipinhao(client, keyword: str, limit: int = 10) -> list[SearchResult]:
    """通过百度搜索视频号内容"""
    results = await search_baidu(client, f"site:channels.qq.com {keyword}", "shipinhao", limit)
    return results
