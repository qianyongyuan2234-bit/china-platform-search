"""多平台搜索聚合器 - 核心调度"""
from __future__ import annotations
import asyncio
import time
from models import SearchResult
from utils.http import HTTPClient

# 平台 handler 映射
HANDLERS = {
    "baidu": ("handlers.baidu", "search_baidu"),
    "weibo": ("handlers.weibo", "search_weibo"),
    "toutiao": ("handlers.toutiao", "search_toutiao"),
    "zhihu": ("handlers.zhihu", "search_zhihu"),
    "sohu": ("handlers.sohu", "search_sohu"),
    "douyin": ("handlers.douyin", "search_douyin"),
    "kuaishou": ("handlers.kuaishou", "search_kuaishou"),
    "xhs": ("handlers.xhs", "search_xhs"),
    "shipinhao": ("handlers.shipinhao", "search_shipinhao"),
    "peoplerail": ("handlers.peoplerail", "search_peoplerail"),
    "bing": ("handlers.bing", "search_bing"),
}

PLATFORM_NAMES = {
    "baidu": "百度",
    "weibo": "微博",
    "toutiao": "今日头条",
    "zhihu": "知乎",
    "sohu": "搜狐",
    "douyin": "抖音",
    "kuaishou": "快手",
    "xhs": "小红书",
    "shipinhao": "视频号",
    "peoplerail": "人民铁道网",
    "bing": "必应",
}


async def search_platform(client: HTTPClient, platform: str, keyword: str, limit: int, days_back: int = None) -> list[SearchResult]:
    """搜索单个平台"""
    module_path, func_name = HANDLERS[platform]
    module = __import__(module_path, fromlist=[func_name])
    func = getattr(module, func_name)

    name = PLATFORM_NAMES.get(platform, platform)
    try:
        results = await func(client, keyword, limit, days_back=days_back)
        print(f"  ✅ {name}: {len(results)} 条")
        return results
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        return []


async def search_all(keyword: str, platforms: list[str] | None = None, limit: int = 10, config: dict | None = None, days_back: int = None) -> list[SearchResult]:
    """
    搜索所有指定平台，返回聚合结果

    Args:
        keyword: 搜索关键词
        platforms: 平台列表，None 表示全部
        limit: 每个平台返回的最大结果数
        config: 配置字典

    Returns:
        聚合后的搜索结果列表
    """
    if platforms is None:
        platforms = list(HANDLERS.keys())

    if config is None:
        config = {}

    search_config = config.get("search", {})
    per_limit = search_config.get("per_platform_limit", limit)

    async with HTTPClient(timeout=search_config.get("timeout", 15)) as client:
        tasks = []
        for p in platforms:
            if p in HANDLERS:
                tasks.append(search_platform(client, p, keyword, per_limit, days_back))
            else:
                print(f"  ⚠️ 未知平台: {p}")

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

    # 全局去重（按 URL 去重，保留先出现的）
    seen_urls: set[str] = set()
    all_results: list[SearchResult] = []
    for results in results_list:
        if isinstance(results, list):
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

    return all_results
