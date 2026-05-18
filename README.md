# China Platform Search Aggregator

在各大中文网络平台搜索关键词，汇总结果并推送到飞书/企业微信。

## 支持平台

| 平台 | 方式 | 内容类型 |
|------|------|----------|
| 百度 | 直接搜索 | 文字、图片 |
| 微博 | 移动端接口 | 文字、图片、视频 |
| 今日头条 | 搜索接口 | 文字、视频 |
| 知乎 | 搜索接口 | 文字 |
| 搜狐 | 新闻搜索 | 文字 |
| 抖音 | 百度 site: 搜索 | 视频 |
| 快手 | 百度 site: 搜索 | 视频 |
| 小红书 | 百度 site: 搜索 | 文字、图片 |
| 视频号 | 百度 site: 搜索 | 视频 |

## 快速开始

```bash
pip install -r requirements.txt

# 基本搜索
python main.py "AI助手"

# 指定平台
python main.py "AI助手" --platforms weibo zhihu

# 推送到飞书
python main.py "AI助手" --notify feishu

# 推送到企业微信
python main.py "AI助手" --notify wecom
```

## 配置

编辑 `config.json` 设置 Webhook 地址。
