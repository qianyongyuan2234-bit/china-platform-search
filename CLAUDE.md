# CLAUDE.md — 中文多平台关键词搜索聚合工具

> 本文件为 Claude Code 提供项目上下文。最后更新：2026-06-05。

## 项目概览

这是一个**中文多平台关键词搜索聚合工具**，输入关键词，并发搜索 10 个中文内容平台，汇总结果并可选推送到飞书/企业微信。

主要使用场景：铁路系统舆情监控、品牌监测、行业情报收集。

## 架构

```
main.py（CLI 入口，argparse）
  └── aggregator.py（并发调度，asyncio.gather）
        ├── HTTPClient（utils/http.py）—— httpx.AsyncClient，UA 随机池
        ├── handlers/baidu.py —— 核心搜索引擎
        │     ├── 直接搜索：抓取 m.baidu.com/s 结果页，BeautifulSoup 解析
        │     └── site: 搜索：其他 handler 通过 platform 参数调用
        ├── handlers/sohu.py —— 独立引擎（搜狗 sogou.com/web）
        └── handlers/weibo.py / toutiao.py / zhihu.py / douyin.py / ...
              └── 均为代理 handler：调用 baidu.search_baidu(client, keyword, limit, days_back, platform="xxx")
        └── utils/notify.py —— curl 调飞书/企微 webhook
```

### 核心模式：百度 `site:` 代理

绝大多数平台没有公开搜索 API，且反爬严格。统一通过百度 `site:` 搜索间接实现：

1. `baidu.py` 的 `SITE_MAP` 字典维护 `platform → (中文名, site:域名)` 映射
2. 被调用时拼接查询 `site:域名 关键词`
3. 各平台 handler（如 `weibo.py`）只有 3-5 行代码，直接代理到 `search_baidu`

### 数据流

```
用户输入关键词
  → main.py 解析参数
  → aggregator.search_all() 创建 HTTPClient → 并发调用各 handler
  → 每个 handler 返回 list[SearchResult]
  → aggregator 合并 + URL 去重
  → 终端 Rich 表格展示 / JSON 导出 / 飞书推送
```

### 关键文件

| 文件 | 作用 | 注意事项 |
|------|------|----------|
| `main.py` | CLI 入口 | argparse，不要写业务逻辑 |
| `aggregator.py` | 核心调度 | `HANDLERS` 和 `PLATFORM_NAMES` 是新平台注册点 |
| `handlers/baidu.py` | 百度搜索引擎 | `SITE_MAP`、`_HREF_SELECTORS`、`_parse_baidu_item` |
| `handlers/sohu.py` | 搜狐独立引擎 | 通过搜狗搜索，不依赖 baidu.py |
| `utils/http.py` | HTTP 客户端 | `HTTPClient` 封装 httpx，自动重试 |
| `utils/notify.py` | 飞书/企微推送 | 用 curl（非 httpx），绕过系统代理 |
| `utils/helpers.py` | 工具函数 | 百度跳转链接解析、HTML 清洗 |
| `models.py` | 数据模型 | `SearchResult` dataclass |
| `config.json` | 运行时配置 | webhook URL 是生产机密，不要写进代码 |

## 编码规范

### Python 版本

- 目标：**Python 3.9+**（兼容性），实际运行：Python 3.14
- 使用 `from __future__ import annotations` 支持延迟求值类型注解

### 风格

- **4 空格缩进**，UTF-8 编码
- **中文注释**（项目受众是中文用户）
- **Google docstring 风格**：`Args:` / `Returns:` / `Raises:`
- 类型注解使用现代语法：`list[SearchResult]`、`dict | None`、`str | None`

### 异步规范

- 所有 handler 函数必须是 `async def`
- 所有 HTTP 请求通过 `HTTPClient.get()` 发出
- `aggregator.py` 用 `asyncio.gather()` 并发调度
- 不要在 handler 内部创建新的 `httpx.AsyncClient`

### 依赖库

| 库 | 用途 | 版本 |
|----|------|------|
| `httpx` | HTTP 客户端（AsyncClient） | >=0.27.0 |
| `beautifulsoup4` | HTML 解析 | >=4.12.0 |
| `rich` | 终端表格展示 | >=13.0.0 |
| `aiofiles` | 异步文件操作 | >=24.0.0 |

不要引入新的重依赖。优先使用标准库。

## 关键约定

### 1. Handler 函数签名

所有平台 handler 必须统一签名：

```python
async def search_xxx(
    client,          # HTTPClient 实例
    keyword: str,     # 搜索关键词
    limit: int = 10,  # 返回结果数上限
    days_back: int = None  # 时间过滤（None = 不限）
) -> list[SearchResult]:
```

### 2. 配置与代码分离

- `config.json` 中的 **webhook URL 绝不要写进任何 .py 文件**
- 不要将真实 URL 写入注释或 docstring
- 代码中只用 `config.get("webhook", {})` 读取

### 3. webhook 推送用 curl

`notify.py` 使用 `subprocess.run(["curl", ...])` 而非 httpx，因为 httpx 经过系统代理无法连接飞书服务器。新增通知渠道沿用此模式。

### 4. 添加新平台 checklist

添加新平台（如 `bilibili`）需要改动 4 处：

1. **`handlers/bilibili.py`** — 新建 handler，代理到 `baidu.search_baidu(platform="bilibili")`
2. **`handlers/baidu.py`** → `SITE_MAP` — 添加 `"bilibili": ("哔哩哔哩", "site:bilibili.com")`
3. **`aggregator.py`** → `HANDLERS` + `PLATFORM_NAMES` — 注册 handler 路径和中文名
4. **`config.json`** → `search.platforms` — 添加到默认平台列表

新平台自动继承时间过滤（`--days`）和百度链接解析。

### 5. 不修改的文件

- `config.json` 的 webhook URL — 生产配置
- `BUILD_JOURNAL.md` — 开发日志，历史记录

## 测试命令

```bash
# 最简测试：只搜百度，每平台 3 条
python main.py "测试" --platforms baidu --limit 3

# 全平台搜索
python main.py "铁路"

# 验证飞书 webhook 连通性（不触发搜索）
python main.py --check-webhook feishu

# 搜索 + 飞书推送
python main.py "高铁" --notify feishu --days 7

# 详细模式
python main.py "春怨" -v

# 指定多个平台
python main.py "AI" --platforms weibo zhihu toutiao

# 导出 JSON
python main.py "铁路" --output results.json
```

## Git 工作流

- 主分支：`main`
- 远程：`git@github.com:qianyongyuan2234-bit/china-platform-search.git`（SSH）
- 提交信息用中文描述改动
