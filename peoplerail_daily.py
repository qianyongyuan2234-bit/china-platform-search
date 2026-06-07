#!/usr/bin/env python3
"""人民铁道数字报第2版(综合版)每日抓取 + 飞书推送

独立脚本，仅依赖 Python 3 标准库。每天抓取《人民铁道》数字报第2版
所有文章，提取标题+摘要+链接，推送到飞书。

用法:
    python3 peoplerail_daily.py                    # 抓取当天并推送
    python3 peoplerail_daily.py --dry-run          # 只打印不推送
    python3 peoplerail_daily.py --date 2026-06-05  # 指定日期

数字报 URL 格式:
    版面页: https://peoplerail.com/newszb/html/{年}-{月}/{日}/node_2.htm
    文章页: https://peoplerail.com/newszb/html/{年}-{月}/{日}/content_2_XXXXX.htm
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────────

BASE_URL = "https://peoplerail.com/newszb/html"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
FETCH_TIMEOUT = 15       # 单次 HTTP 请求超时（秒）
SUMMARY_MAX_CHARS = 200  # 摘要最大字数
CARD_MAX_BYTES = 28000   # 飞书卡片内容截断阈值（字符数）


# ── URL 构造 ──────────────────────────────────────────────────────

def _path_date(d: date) -> str:
    """date → URL 路径段，如 date(2026,6,6) → '2026-06/06'"""
    return d.strftime("%Y-%m/%d")


def node_page_url(d: date) -> str:
    """构造第2版版面页 URL"""
    return f"{BASE_URL}/{_path_date(d)}/node_2.htm"


def article_page_url(d: date, relative_path: str) -> str:
    """构造文章详情页完整 URL"""
    return f"{BASE_URL}/{_path_date(d)}/{relative_path}"


# ── HTTP 工具 ─────────────────────────────────────────────────────

def _make_opener() -> urllib.request.OpenerDirector:
    """创建不经过系统代理的 opener（ProxyHandler 为空）"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _clear_proxy_env() -> None:
    """清除所有代理相关环境变量"""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy"):
        os.environ.pop(var, None)


def fetch_html(url: str, opener: urllib.request.OpenerDirector) -> str | None:
    """GET 请求，返回解码后的 HTML 文本；404 或其他错误返回 None。

    Args:
        url: 目标 URL
        opener: 无代理 opener

    Returns:
        HTML 字符串，或 None（404 / 网络错误 / 解码失败）
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        # 404 是正常情况（当天报纸未出），不打印报错
        if e.code != 404:
            print(f"  ⚠️ HTTP {e.code}: {url}")
        return None
    except Exception as e:
        print(f"  ⚠️ 请求失败: {e}")
        return None

    # 解码：优先 UTF-8，失败则从 Content-Type 取 charset，再失败用 GBK
    content_type = resp.headers.get("Content-Type", "")
    charsets = ["utf-8"]
    m = re.search(r'charset=([\w-]+)', content_type)
    if m:
        charsets.insert(0, m.group(1))
    charsets.append("gbk")

    for enc in charsets:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # 最终兜底
    return raw.decode("utf-8", errors="replace")


# ── HTML 解析 ─────────────────────────────────────────────────────

def _strip_html(html: str) -> str:
    """移除 HTML 标签，解码实体，压缩空白。"""
    text = re.sub(r'<br\s*/?\s*>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)
    text = text.replace('\r', '\n')
    # 保留单个换行，压缩多层空行
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def extract_articles_from_node(html: str) -> list[dict]:
    """从版面页 HTML 提取文章列表（标题 + 摘要 + 相对链接）。

    版面页结构（<li class="listH …">）：
        <a href="content_2_65548.htm" class="listTitle ellipsis">标题</a>
        <span class="ellipsis-2 listDesc">摘要</span>

    Returns:
        [{"title": str, "href": str, "node_summary": str}, ...]
    """
    articles = []
    # 匹配每个 listH 块
    blocks = re.finditer(
        r'<li\s+class="listH[^"]*"[^>]*>(.*?)</li>',
        html, re.DOTALL | re.IGNORECASE
    )

    for block in blocks:
        content = block.group(1)
        # 提取标题
        title_m = re.search(
            r'<a[^>]*href="(content_\d+_\d+\.htm)"[^>]*class="[^"]*listTitle[^"]*"[^>]*>(.*?)</a>',
            content, re.DOTALL | re.IGNORECASE
        )
        if not title_m:
            continue
        href = title_m.group(1)
        title = _strip_html(title_m.group(2))

        if not title:
            continue

        # 提取版面页自带摘要
        desc_m = re.search(
            r'<span[^>]*class="[^"]*listDesc[^"]*"[^>]*>(.*?)</span>',
            content, re.DOTALL | re.IGNORECASE
        )
        node_summary = _strip_html(desc_m.group(1)) if desc_m else ""

        articles.append({
            "title": title,
            "href": href,
            "node_summary": node_summary,
        })

    return articles


def extract_body_text(html: str) -> str:
    """从文章详情页提取正文纯文本。

    尝试顺序：
    1. <div id="articleContent" class="infoContent">…</div>
    2. <founder-content>…</founder-content>
    3. <article>…</article>
    4. 整页 body 兜底
    """
    patterns = [
        # 人民铁道数字报实际结构
        r'<div\s+[^>]*id="articleContent"[^>]*>(.*?)</div>\s*(?:<div|<script)',
        # founder-content 标签（某些数字报系统使用）
        r'<founder-content[^>]*>(.*?)</founder-content>',
        # 通用 article 标签
        r'<article[^>]*>(.*?)</article>',
    ]

    for pat in patterns:
        m = re.search(pat, html, re.DOTALL | re.IGNORECASE)
        if m:
            text = _strip_html(m.group(1))
            if len(text) >= 20:
                return text

    # 兜底：从 body 提取全部文本
    body_m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if body_m:
        return _strip_html(body_m.group(1))
    return _strip_html(html)


def make_summary(text: str, max_chars: int = SUMMARY_MAX_CHARS) -> str:
    """从正文截取前 max_chars 字作为摘要。

    Args:
        text: 全文纯文本
        max_chars: 最大字符数

    Returns:
        截断后的摘要字符串（过长时末尾加 …）
    """
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= max_chars:
        return text
    # 直接按字符截断（中文没有单词边界）
    return text[:max_chars].rstrip() + "…"


# ── 飞书推送 ──────────────────────────────────────────────────────

def _read_feishu_webhook() -> str:
    """从项目 config.json 读取飞书 webhook URL"""
    config_path = Path(__file__).resolve().parent / "config.json"
    if not config_path.exists():
        print(f"⚠️ 找不到配置文件: {config_path}")
        return ""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config.get("webhook", {}).get("feishu", "")
    except Exception as e:
        print(f"⚠️ 读取 config.json 失败: {e}")
        return ""


def _escape_md(text: str) -> str:
    """转义飞书 Markdown 中的特殊字符（**、链接语法等不受影响）。"""
    # 对 markdown 特殊字符做基本转义
    return text.replace("\\", "\\\\").replace("`", "\\`")


def send_feishu(webhook_url: str, date_str: str,
                articles: list[dict]) -> bool:
    """用飞书交互卡片（interactive card）推送文章列表。

    卡片支持加粗标题 + 可点击链接 + 摘要文本。
    内容过长时自动截断。

    Args:
        webhook_url: 飞书机器人 webhook 地址
        date_str: 日期字符串，如 "2026-06-06"
        articles: 文章列表

    Returns:
        是否发送成功
    """
    # 构建每篇文章的 markdown 块
    blocks = []
    for i, art in enumerate(articles):
        title = _escape_md(art["title"])
        block = f"**{i + 1}. {title}**\n"
        summary = art.get("summary") or art.get("node_summary", "")
        if summary:
            # 摘要中可能有 markdown 特殊字符，做轻度转义
            summary = _escape_md(summary)
            block += f"{summary}\n"
        block += f"[🔗 阅读全文]({art['url']})"
        blocks.append(block)

    md_content = "\n\n".join(blocks)

    # 截断（飞书卡片内容有长度限制）
    if len(md_content) > CARD_MAX_BYTES:
        md_content = md_content[:CARD_MAX_BYTES]
        # 回退到最后一个完整行
        last_nl = md_content.rfind("\n")
        if last_nl > CARD_MAX_BYTES * 0.8:
            md_content = md_content[:last_nl]
        md_content += "\n\n... 内容过长已截断"

    payload = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"📰 人民铁道·综合版 {date_str}",
                },
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": md_content,
                },
                {
                    "tag": "hr",
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": (
                                f"共 {len(articles)} 篇文章"
                                f" · {datetime.now().strftime('%H:%M')}"
                            ),
                        }
                    ],
                },
            ],
        },
    }

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-w", "\n%{http_code}",
                "-X", "POST", webhook_url,
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload, ensure_ascii=False),
            ],
            capture_output=True, text=True, timeout=FETCH_TIMEOUT,
        )
    except FileNotFoundError:
        print("❌ 未找到 curl 命令，请确认已安装")
        return False
    except Exception as e:
        print(f"❌ curl 执行失败: {e}")
        return False

    output = result.stdout.strip()
    parts = output.rsplit("\n", 1)
    status_code = int(parts[-1]) if len(parts) > 1 else 0
    body = parts[0] if len(parts) > 1 else output

    if status_code == 200:
        print("✅ 飞书推送成功")
        return True
    else:
        print(f"❌ 飞书推送失败: HTTP {status_code}\n   {body[:200]}")
        return False


# ── 终端输出 ──────────────────────────────────────────────────────

def print_articles(articles: list[dict], date_str: str) -> None:
    """终端美观打印文章列表。"""
    print()
    print("=" * 64)
    print(f"  📰 人民铁道·综合版  {date_str}")
    print(f"  📊 共 {len(articles)} 篇文章")
    print("=" * 64)
    print()

    for i, art in enumerate(articles, 1):
        print(f"  [{i}] {art['title']}")
        summary = art.get("summary") or art.get("node_summary", "")
        if summary:
            print(f"      {summary}")
        print(f"      🔗 {art['url']}")
        print()


# ── 主流程 ────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="人民铁道数字报第2版(综合版)每日抓取 + 飞书推送"
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="指定日期，格式 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="只打印文章列表，不推送到飞书",
    )
    parser.add_argument(
        "--no-detail", action="store_true",
        help="不抓取详情页，直接用版面页摘要（速度更快）",
    )
    args = parser.parse_args()

    # ── 解析日期 ──
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ 日期格式错误: {args.date}，应为 YYYY-MM-DD")
            sys.exit(1)
    else:
        target_date = date.today()

    date_str = target_date.strftime("%Y-%m-%d")
    print(f"📅 目标日期: {date_str}")

    # ── 准备 HTTP 环境 ──
    _clear_proxy_env()
    opener = _make_opener()

    # ── Step 1: 抓取版面页 ──
    node_url = node_page_url(target_date)
    print(f"🌐 请求版面页: {node_url}")

    html = fetch_html(node_url, opener)
    if html is None:
        print(f"\n📭 当天 ({date_str}) 报纸尚未发布（版面页 404 或无法访问）")
        print("   提示: 人民铁道可能周末/节假日休刊，可尝试 --date 指定更早日期")
        sys.exit(0)

    # ── Step 2: 提取文章列表 ──
    articles = extract_articles_from_node(html)
    print(f"📋 版面页提取到 {len(articles)} 篇文章")

    if not articles:
        print("⚠️ 未能从版面页提取到文章，HTML 结构可能已变化")
        # 输出 HTML 片段辅助排查
        print("\n--- 版面页 HTML 前 1500 字符（调试）---")
        print(html[:1500])
        sys.exit(0)

    # ── Step 3: 抓取详情页提取摘要 ──
    if not args.no_detail:
        for i, art in enumerate(articles):
            url = article_page_url(target_date, art["href"])
            title_preview = art["title"][:30]
            print(f"  [{i + 1}/{len(articles)}] {title_preview}...")

            detail_html = fetch_html(url, opener)
            if detail_html:
                body_text = extract_body_text(detail_html)
                art["summary"] = make_summary(body_text)
            else:
                # 详情页失败，使用版面页自带摘要
                art["summary"] = art.get("node_summary", "")

            art["url"] = url
    else:
        # --no-detail: 直接用版面页摘要
        for art in articles:
            art["summary"] = art.get("node_summary", "")
            art["url"] = article_page_url(target_date, art["href"])

    # ── Step 4: 终端打印 ──
    print_articles(articles, date_str)

    # ── Step 5: 飞书推送 ──
    if args.dry_run:
        print("🔍 --dry-run 模式，跳过飞书推送")
        return

    webhook_url = _read_feishu_webhook()
    if not webhook_url:
        print("⚠️ config.json 中 webhook.feishu 为空，跳过推送")
        print("   请在 config.json 中配置飞书机器人 webhook 地址")
        return

    print("📤 推送飞书...")
    send_feishu(webhook_url, date_str, articles)


if __name__ == "__main__":
    main()
