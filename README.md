# 中文多平台关键词搜索聚合工具

一键在 **12 个中文平台** 搜索关键词，聚合结果并推送到飞书/企业微信。

内置支持：百度、微博、今日头条、知乎、搜狐、抖音、快手、小红书、视频号、人民铁道网、必应、DuckDuckGo。

## 使用场景

- **舆情监控**：每天定时搜索铁路车站、企业品牌等关键词，推送到飞书群
- **应急搜索**：突发新闻时快速扫描各平台报道
- **竞品分析**：持续跟踪竞品在各平台的最新动态
- **行业情报**：关注特定行业（铁路、金融、科技等）的多平台信息

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

依赖项：`httpx`（HTTP 请求）、`rich`（终端展示）、`aiofiles`（文件处理）。HTML 解析使用标准库 `re`（正则），无需额外依赖。

### 2. 配置文件

编辑 `config.json`，填入飞书 webhook 地址：

```json
{
  "webhook": {
    "feishu": "https://open.feishu.cn/open-apis/bot/v2/hook/你的hook",
    "wecom": ""
  },
  "search": {
    "platforms": ["baidu", "weibo", "toutiao", "zhihu", "sohu", "xhs", "douyin", "kuaishou", "shipinhao", "peoplerail", "bing", "ddg"],
    "per_platform_limit": 10,
    "timeout": 15
  }
}
```

| 字段 | 说明 |
|------|------|
| `webhook.feishu` | 飞书机器人 webhook 地址 |
| `webhook.wecom` | 企业微信机器人 webhook 地址（可选） |
| `search.platforms` | 默认搜索的平台列表 |
| `search.per_platform_limit` | 每个平台返回的最大结果数 |
| `search.timeout` | HTTP 请求超时时间（秒） |

> ⚠️ **重要**：webhook URL 是生产密钥，不要提交到代码仓库。`.gitignore` 已忽略 `config.json` 的变化（如有需要请自行确认）。

### 3. 运行

```bash
# 搜索全部 12 个平台
python main.py "铁路安全"

# 搜索最近 7 天内容
python main.py "高铁" --days 7

# 只搜索指定平台
python main.py "火车票" --platforms baidu weibo zhihu

# 搜索并推送到飞书
python main.py "铁路事故" --notify feishu

# 搜索最近 7 天 + 飞书推送
python main.py "车站" --notify feishu --days 7

# 每平台只取 3 条结果
python main.py "春怨" --limit 3

# 保存结果到 JSON 文件
python main.py "铁路" --output results.json

# 验证飞书 webhook 连通性
python main.py --check-webhook feishu
```

## 支持平台

| # | 平台 | 搜索方式 | Handler 文件 |
|---|------|----------|-------------|
| 1 | 百度 | 直接搜索 m.baidu.com | `handlers/baidu.py` |
| 2 | 微博 | 百度 site:weibo.com | `handlers/weibo.py` |
| 3 | 今日头条 | 百度 site:toutiao.com | `handlers/toutiao.py` |
| 4 | 知乎 | 百度 site:zhihu.com | `handlers/zhihu.py` |
| 5 | 搜狐 | 搜狗 site:sohu.com | `handlers/sohu.py` |
| 6 | 抖音 | 百度 site:douyin.com | `handlers/douyin.py` |
| 7 | 快手 | 百度 site:kuaishou.com | `handlers/kuaishou.py` |
| 8 | 小红书 | 百度 site:xiaohongshu.com | `handlers/xhs.py` |
| 9 | 视频号 | 百度 site:channels.qq.com | `handlers/shipinhao.py` |
| 10 | 人民铁道网 | 百度 site:peoplerail.com | `handlers/peoplerail.py` |
| 11 | 必应 | 独立引擎 cn.bing.com（回退链第三级） | `handlers/bing.py` |
| 12 | DuckDuckGo | 独立引擎 html.duckduckgo.com（回退链终点） | `handlers/ddg.py` |

## 添加新平台

要添加一个新平台（如哔哩哔哩），只需 4 步：

### Step 1：创建 handler 文件

新建 `handlers/bilibili.py`：

```python
"""哔哩哔哩搜索 - 通过百度搜索 B 站内容"""
from models import SearchResult
from handlers.baidu import search_baidu


async def search_bilibili(client, keyword: str, limit: int = 10,
                          days_back: int = None) -> list[SearchResult]:
    """通过百度 site: 搜索哔哩哔哩内容"""
    return await search_baidu(
        client, keyword, limit,
        days_back=days_back, platform="bilibili"
    )
```

### Step 2：在 baidu.py 注册站点

在 `handlers/baidu.py` 的 `SITE_MAP` 字典中添加：

```python
SITE_MAP = {
    # ... 已有条目 ...
    "bilibili": ("哔哩哔哩", "site:bilibili.com"),
}
```

### Step 3：在 aggregator.py 注册

在 `aggregator.py` 的 `HANDLERS` 和 `PLATFORM_NAMES` 中添加：

```python
HANDLERS = {
    # ... 已有条目 ...
    "bilibili": ("handlers.bilibili", "search_bilibili"),
}

PLATFORM_NAMES = {
    # ... 已有条目 ...
    "bilibili": "哔哩哔哩",
}
```

### Step 4：在 config.json 中启用

```json
{
  "search": {
    "platforms": [
      "...",
      "bilibili"
    ]
  }
}
```

完成！新平台会自动继承百度的**时间过滤**（`--days`）和**链接解析**能力，无需额外编码。

## 搜索原理

```
main.py (CLI 入口)
  └── aggregator.py (并发调度，asyncio.gather)
        ├── baidu.py (核心：抓取 m.baidu.com/s 结果页，正则解析)
        ├── sogou.py (二级回退：搜狗 sogou.com/web)
        ├── bing.py  (三级回退：必应 cn.bing.com/search)
        ├── ddg.py   (四级终点：DuckDuckGo html.duckduckgo.com/html/)
        ├── sohu.py  (搜狐：通过搜狗 site:sohu.com)
        └── weibo.py / toutiao.py / zhihu.py / ...  (代理：调用 baidu.search_baidu 传 site: 参数)
```

**百度 `site:` 搜索策略**：对于没有公开搜索 API 的平台（抖音、快手、小红书等），通过 `site:域名 关键词` 的方式委托百度搜索。百度已经爬取了这些网站的内容，我们只需解析百度的结果页。代价是时效性依赖百度收录速度。

**多级回退链**：当百度被封锁或触发反爬时，自动逐级回退：`百度 → 搜狗 → 必应 → DuckDuckGo`。每一级失败时自动尝试下一级，DDG 是回退终点（失败时返回空列表）。

## 常见问题

**Q: 为什么有些平台结果很少？**
A: 百度 `site:` 搜索依赖百度对该网站的收录情况。收录越少，可搜到的结果越少。

**Q: 飞书推送失败怎么办？**
A: 先运行 `python main.py --check-webhook feishu` 验证 webhook 连通性。确认 webhook URL 正确且未过期。本项目使用 `curl` 直接发送（绕过系统代理）。

**Q: 如何实现定时自动搜索？**
A: 配置 cron job 或类似调度工具：
```bash
# 每天 9:30 和 15:30 执行（crontab）
30 9,15 * * * cd /path/to/project && python main.py "铁路" --notify feishu --days 7
```

## 项目结构

```
├── main.py                  # CLI 入口
├── aggregator.py            # 核心调度
├── models.py                # 数据模型
├── config.json              # 配置文件
├── requirements.txt         # 依赖声明
├── requirements.lock        # 精确依赖版本
├── CLAUDE.md                # 项目架构文档
├── tests/                   # 单元测试（纯函数，不联网）
│   ├── __init__.py
│   ├── test_helpers.py      # helpers 工具函数
│   ├── test_normalize_title.py  # 标题归一化
│   ├── test_baidu_parse.py  # 百度 HTML 解析
│   └── test_bing.py         # 必应解析 + 标题清洗
├── handlers/
│   ├── baidu.py             # 百度搜索核心
│   ├── sogou.py             # 搜狗回退引擎
│   ├── bing.py              # 必应回退引擎
│   ├── ddg.py               # DuckDuckGo 回退终点
│   ├── sohu.py              # 搜狐（通过搜狗搜索）
│   └── weibo.py / toutiao.py / zhihu.py / ...  # 各平台 handler
└── utils/
    ├── http.py              # HTTP 客户端
    ├── notify.py            # 飞书/企微推送
    └── helpers.py           # URL 解析工具
```

## License

MIT
