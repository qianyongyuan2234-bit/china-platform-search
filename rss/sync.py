#!/usr/bin/env python3
"""精读通道 — RSS 扫描 + 飞书推送

用法:
    python3 rss/sync.py            # 扫描所有源，推送新文章到飞书
    python3 rss/sync.py --dry-run  # 只扫描，不推送、不标记已读
"""

import subprocess
import sys
import json
import urllib.request
import urllib.error
import textwrap
from datetime import datetime

BLOGWATCHER = "/Users/chong/.local/bin/blogwatcher-cli"
WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/44a0afc7-0652-4c82-8f45-8152308369e0"

MAX_ARTICLES_PER_PUSH = 15      # 单次推送最多 15 篇
MAX_CARD_LENGTH = 2500          # 飞书消息单条上限字符数（留余量）


def run_blogwatcher(*args):
    """运行 blogwatcher-cli，返回 stdout"""
    cmd = [BLOGWATCHER] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"blogwatcher-cli 失败: {result.stderr.strip()}")
    return result.stdout


def parse_articles(output):
    """解析 blogwatcher-cli articles 输出，返回文章列表"""
    articles = []
    current = {}
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            if current and "title" in current:
                articles.append(current)
                current = {}
            continue

        # 匹配:   [123] [new] Title here (ID 位数不固定，用搜索定位)
        idx_close = line.find("]")
        if idx_close > 0 and idx_close < 10 and "[new]" in line[idx_close:idx_close+7] or "[old]" in line[idx_close:idx_close+7]:
            if current and "title" in current:
                articles.append(current)
            current = {}
            title = line[idx_close+1:].strip()
            current["title"] = title
            current["is_new"] = "[new]" in line  # line 是整行，含 [new]/[old]
            continue

        if line.startswith("Blog:"):
            current["blog"] = line.replace("Blog:", "").strip()
        elif line.startswith("URL:"):
            current["url"] = line.replace("URL:", "").strip()
        elif line.startswith("Published:"):
            current["date"] = line.replace("Published:", "").strip()
        elif line.startswith("Categories:") and not line.startswith("Categories: ["):
            current["categories"] = line.replace("Categories:", "").strip()

    if current and "title" in current:
        articles.append(current)

    return articles


def format_feishu_card(articles, scan_summary):
    """格式化为飞书消息文本"""
    if not articles:
        return f"📰 精读日报\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n无新文章。"

    lines = [
        f"📰 精读日报",
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"📊 {scan_summary}",
        "",
    ]

    for a in articles[:MAX_ARTICLES_PER_PUSH]:
        blog = a.get("blog", "?")
        title = a.get("title", "无标题")
        url = a.get("url", "")
        date = a.get("date", "?")

        # 截断过长标题
        if len(title) > 80:
            title = title[:77] + "..."

        source_tag = f"【{blog}】"
        lines.append(f"{source_tag} {title}")

    if len(articles) > MAX_ARTICLES_PER_PUSH:
        lines.append(f"...及其他 {len(articles) - MAX_ARTICLES_PER_PUSH} 篇新文章")

    text = "\n".join(lines)
    # 飞书消息单条上限约 3000 字符
    if len(text) > MAX_CARD_LENGTH:
        text = text[:MAX_CARD_LENGTH - 20] + "\n\n...（内容已截断）"

    return text


def push_to_feishu(text):
    """通过 webhook 推送到飞书"""
    payload = json.dumps({
        "msg_type": "text",
        "content": {"text": text},
    }).encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = resp.read().decode("utf-8")
        r = json.loads(result)
        if r.get("code") == 0:
            print("  ✅ 飞书推送成功")
            return True
        else:
            print(f"  ❌ 飞书推送失败: {result}")
            return False
    except urllib.error.URLError as e:
        print(f"  ❌ 飞书推送网络错误: {e}")
        return False


def main():
    dry_run = "--dry-run" in sys.argv

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 精读通道开始扫描...")

    # 1. 扫描
    scan_out = run_blogwatcher("scan")
    # 提取摘要行
    summary_line = ""
    for line in scan_out.strip().split("\n"):
        if "Scanned" in line and ("succeeded" in line or "failed" in line):
            summary_line = line.strip()
            break
    if not summary_line:
        summary_line = "扫描完成"
    print(f"  {summary_line}")

    # 2. 获取新文章（--limit 不支持，获取全部）
    articles_out = run_blogwatcher("articles")
    articles = parse_articles(articles_out)
    new_articles = [a for a in articles if a.get("is_new")]
    print(f"  待推送: {len(new_articles)} 篇")

    if dry_run:
        print("\n  [DRY RUN] 不推送，不标记已读。预览:")
        for a in new_articles[:10]:
            print(f"    [{a.get('blog', '?')}] {a.get('title', '无标题')[:60]}")
        if len(new_articles) > 10:
            print(f"    ...及其他 {len(new_articles) - 10} 篇")
        return 0

    # 3. 推送到飞书
    if new_articles:
        text = format_feishu_card(new_articles, summary_line)
        push_to_feishu(text)

        # 4. 标记已读
        run_blogwatcher("read-all", "--yes")
        print(f"  ✅ 已标记 {len(new_articles)} 篇为已读")
    else:
        print("  无新文章，跳过推送")

    return 0


if __name__ == "__main__":
    sys.exit(main())
