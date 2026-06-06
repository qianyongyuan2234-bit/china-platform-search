"""多平台搜索聚合器 - 核心调度"""
from __future__ import annotations
import asyncio
import re
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
    "ddg": ("handlers.ddg", "search_ddg"),
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
    "ddg": "DuckDuckGo",
}


# ── 标题归一化：用于跨平台去重 ──

# 常见平台尾巴（不同平台的同一篇文章常在标题后附加平台名）
# 注意：更长的后缀排在前面，避免"新浪财经"被"新浪"误匹配
_PLATFORM_SUFFIXES = [
    "新浪财经", "新浪新闻", "新浪科技", "新浪网", "新浪",
    "搜狐新闻", "搜狐网", "搜狐",
    "知乎专栏", "知乎",
    "今日头条", "头条",
    "百度百科", "百度知道", "百度文库",
    "微信公众平台", "公众号",
    "哔哩哔哩", "bilibili",
    "微博正文", "微博",
    "人民铁道网", "铁路网", "人民网",
    "网易新闻", "网易",
    "腾讯新闻", "腾讯网",
    "凤凰资讯", "凤凰网",
    "抖音", "快手", "小红书",
    "百家号", "央视网", "澎湃新闻",
]


def _normalize_title(title: str) -> str:
    """将标题归一化，用于跨平台相似度比较

    归一化规则：
    1. 将常见分隔符统一替换为空格，便于识别结尾的平台尾巴
    2. 循环剥离结尾的已知平台名（按长度降序，优先匹配更长后缀）
    3. 去除所有标点和空白字符
    4. 转小写

    Args:
        title: 原始标题

    Returns:
        归一化后的字符串
    """
    t = title.strip()
    # 步骤1：将常见标题分隔符统一替换为空格
    # 注意：- 放在字符类开头，避免被解释为范围操作符（原 bug 根因）
    t = re.sub(r'[-_|—–·•／/\s｜,，、。:：；;]+', ' ', t)
    t = t.strip()
    # 步骤2：循环剥离结尾的平台名后缀
    # _PLATFORM_SUFFIXES 已按长度降序排列（长后缀优先）
    changed = True
    while changed:
        changed = False
        for suffix in _PLATFORM_SUFFIXES:
            # 匹配：可选分隔空格 + 平台名 + 字符串结尾
            m = re.search(r'(?:\s+|^)' + re.escape(suffix) + r'$', t)
            if m:
                t = t[:m.start()].strip()
                changed = True
                break  # 每次只剥一个，重新扫描以防重叠
    # 步骤3：去除所有标点和空白，转小写
    t = re.sub(r'[^\w]', '', t)
    return t.lower()


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

    # 二次去重：按标题归一化去重（同一新闻在不同平台 URL 不同但标题相同）
    seen_titles: set[str] = set()
    deduped: list[SearchResult] = []
    for r in all_results:
        norm = _normalize_title(r.title)
        # 空标题不过滤（保留原始数据）
        if norm and norm in seen_titles:
            continue
        if norm:
            seen_titles.add(norm)
        deduped.append(r)

    if len(deduped) < len(all_results):
        print(f"  🔄 标题去重: {len(all_results)} → {len(deduped)} 条（移除 {len(all_results) - len(deduped)} 条疑似重复）")

    return deduped
