# China Platform Search Aggregator — 构建日志

## 项目缘起

**背景**：在铁路系统媒体部工作，日常需要监控多个中文平台上与铁路相关的舆情和最新信息。之前靠人工一个个打开百度、微博、知乎……搜索关键词，效率极低。

**需求**：一个命令搞定全部平台搜索，结果推到飞书群里，设成定时任务每天自动跑。

**核心场景**：
1. 手动应急搜索：输入关键词，看10个平台的结果
2. 定时监控：每天9:30和15:30自动搜索东北线15个车站的新闻，推送到飞书
3. 热榜分析：关注铁路行业的最新话题

---

## 架构总览

```
china-platform-search/
├── main.py                  # CLI 入口，argparse 解析参数
├── aggregator.py            # 核心调度器，并发搜索所有平台
├── models.py                # SearchResult 数据模型
├── config.json              # 飞书 webhook 地址 + 搜索配置
├── requirements.txt         # 依赖：httpx, beautifulsoup4, rich
├── handlers/
│   ├── __init__.py
│   ├── baidu.py             # 📍 核心引擎——百度搜索 + site: 搜索
│   ├── weibo.py             # 微博   (通过百度 site:weibo.com)
│   ├── toutiao.py           # 今日头条 (通过百度 site:toutiao.com)
│   ├── zhihu.py             # 知乎   (通过百度 site:zhihu.com)
│   ├── sohu.py              # 搜狐   (通过搜狗搜索搜狐站点)
│   ├── douyin.py            # 抖音   (通过百度 site:v.douyin.com)
│   ├── kuaishou.py          # 快手   (通过百度 site:www.kuaishou.com)
│   ├── xhs.py              # 小红书  (通过百度 site:xiaohongshu.com)
│   ├── shipinhao.py         # 视频号  (通过百度 site:channels.qq.com)
│   └── peoplerail.py        # 人民铁道网 (通过百度 site:peoplerail.com)
└── utils/
    ├── http.py              # HTTP 客户端（ua 随机池, httpx）
    ├── notify.py            # 飞书/企业微信推送（curl 直接调用）
    └── helpers.py           # 百度 URL 解析（短链还原、HTML 清洗）
```

### 搜索模式

**模式一：直接 API / 页面抓取**
- **百度**：抓取 `baidu.com/s` 搜索结果页，`BeautifulSoup` 解析标题、摘要、链接，处理百度跳转链接
- **搜狐**：通过搜狗搜索 `sogou.com/web` 抓取搜狐站点内容

**模式二：百度 site: 间接搜索**
- 微博、今日头条、知乎、抖音、快手、小红书、视频号、人民铁道网
- 原理：`site:域名 + 关键词` 交给百度搜索，百度已经爬过这些网站的内容
- 优势：不需要每个平台都去适配反爬、不需要 API Key
- 缺点：结果依赖百度收录时效性

---

## 版本演进

### v1.0 — MVP（初始版本）

- 10 个平台的基础搜索能力
- `python main.py "关键词"` 一键搜索全部
- `--platforms baidu weibo` 指定部分平台
- `--notify feishu` 推送到飞书
- Rich 终端表格展示
- 百度 URL 短链还原（`unshorten_baidu_url`）
- 移动端 User-Agent 随机池 → 绕过部分反爬

#### 关键设计决策

**为什么用百度 site: 搜索而非每个平台自建 handler？**
- 工期评估：自建 handler 需要处理每个平台的登录、反爬、API 限制
- 抖音/快手/小红书都没有公开的搜索 API
- 百度 site: 搜索相当于"免费代理"，百度已经爬过这些站，我们只需要解析百度的结果
- 代价是时效性略差（百度收录有延迟），但对铁路舆情监控场景够用

**为什么用 curl 而非 httpx 发飞书 webhook？**
- httpx 走了代理，而代理与飞书服务器不通
- curl 直接发送不经过代理，稳定可靠
- 把 `send_feishu` 和 `send_wecom` 封装在 `notify.py` 中，用 `subprocess.run` 调用 curl

### v1.1 — 时间过滤（`--days` 参数）

**需求**：监控铁路车站舆情时只看最近 N 天的新内容，不要老结果。

**改造**：
- 全链路透传 `days_back` 参数：`main.py` → `aggregator.py` → 每个 handler
- 百度搜索用 `gpc=stf={start_ts},{end_ts}|stftype=1` 参数实现时间过滤
- 所有基于百度 site: 搜索的平台自动继承时间过滤能力
- handler 签名统一改为 `async def search_xxx(client, keyword, limit, days_back=None)`

**改动量**：10 个 handler + aggregator + main.py，共改 11 个文件，+38/-22 行。

### v1.2 — 人民铁道网接入（最新改动）

**需求**：铁路系统的官方媒体「人民铁道网」(peoplerail.com) 需要纳入搜索范围。

**实现**：8 行代码的极简 handler：
```python
async def search_peoplerail(client, keyword, limit=10, days_back=None):
    results = await search_baidu(client, keyword, limit, days_back=days_back, platform="peoplerail")
    return results
```

- 在 `baidu.py` 的 `SITE_MAP` 中注册 `"peoplerail": ("人民铁道网", "site:peoplerail.com")`
- 在 `aggregator.py` 的 `HANDLERS` 和 `PLATFORM_NAMES` 中注册
- 在 `config.json` 的 `platforms` 列表中追加
- 飞书消息自动识别为文字类型（peoplerail 不在 douyin/kuaishou/shipinhao 列表中）

---

## 部署 & 自动化

### 定时任务（Cron Job）

用 Hermes Agent 的 `cronjob` 功能部署了铁路车站监控任务：

- **任务名**：铁路车站监测-东北线
- **调度**：每天 9:30、15:30（`30 9,15 * * *`）
- **搜索对象**：14 个东北线铁路车站（白城站、乌兰浩特站、松原站、大安站、洮南站、通榆站、太平川站、镇赉站、阿尔山站、长山屯站、查干湖站、新肇站、太阳升站、乾安站）
- **时间范围**：最近 7 天
- **推送方式**：飞书
- **工作目录**：`/Users/chong/projects/china-platform-search/`
- **加载 skill**：`china-platform-search`（确保 cron 运行时能正确引用项目路径）

### GitHub

- **远程仓库**：`git@github.com:qianyongyuan2234-bit/china-platform-search.git`
- **推送方式**：SSH key（`~/.ssh/id_hermes`）
- **本地提交**：1 个 commit `1835fff`，当前有 11 个文件修改未提交（v1.1 + v1.2 的改动）

---

## 遇到的问题 & 解决

| 问题 | 解决 |
|------|------|
| httpx 走代理连不上飞书 | 改为 curl 直接调用，绕过代理 |
| 百度搜索结果链接是跳转链接 | 实现 `unshorten_baidu_url` 函数：先尝试 query 参数解码，再跟随重定向 |
| 百度搜索结果页 HTML 结构多变 | 用多级 CSS 选择器（`_HREF_SELECTORS`），按优先级尝试 |
| 抖音/快手/小红书无反爬 API | 走百度 site: 间接搜索 |
| Hermes 代理导致 webhook 失败 | notify.py 全用 curl 而非 httpx |

---

## 使用方式

```bash
# 搜索全部 10 个平台
python main.py "铁路"

# 只看最近 3 天
python main.py "高铁" --days 3

# 指定平台
python main.py "铁路" --platforms baidu weibo zhihu

# 搜索 + 飞书推送
python main.py "铁路事故" --notify feishu

# 搜索 + 保存到文件
python main.py "铁路" --output results.json
```

### 配置

编辑 `config.json`：
```json
{
  "webhook": {
    "feishu": "https://open.feishu.cn/open-apis/bot/v2/hook/你的hook",
    "wecom": ""
  },
  "search": {
    "platforms": ["baidu", "weibo", "toutiao", "zhihu", "sohu", "xhs", "douyin", "kuaishou", "shipinhao", "peoplerail"],
    "per_platform_limit": 10,
    "timeout": 15
  }
}
```

---

## 技术栈

| 组件 | 选择 |
|------|------|
| Python | 3.10+ |
| HTTP | httpx（AsyncClient） |
| HTML 解析 | BeautifulSoup 4 |
| 终端展示 | Rich |
| webhook | curl（绕过代理） |
| 定时调度 | Hermes Agent cronjob |
| 版本控制 | Git → GitHub (SSH) |
