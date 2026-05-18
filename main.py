#!/usr/bin/env python3
"""
中文多平台关键词搜索聚合工具
在微博、今日头条、百度、知乎、搜狐、抖音、快手、小红书、视频号等平台搜索
结果可推送到飞书或企业微信群
"""
import json
import asyncio
import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from aggregator import search_all
from utils.notify import send_notification
from utils.http import HTTPClient

console = Console()


def load_config(path: str = "config.json") -> dict:
    p = Path(__file__).parent / path
    if p.exists():
        return json.loads(p.read_text())
    return {}


def print_results(results):
    """在终端打印搜索结果"""
    if not results:
        console.print("\n[red]❌ 未找到任何结果[/red]\n")
        return

    # 按平台分组
    from collections import defaultdict
    groups = defaultdict(list)
    for r in results:
        groups[r.platform].append(r)

    total = len(results)
    console.print(f"\n[bold green]🔍 共找到 {total} 条结果，来自 {len(groups)} 个平台[/bold green]\n")

    for platform, items in groups.items():
        console.print(f"[bold cyan]━━━ {platform} ({len(items)}条) ━━━[/bold cyan]")

        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("类型", width=6)
        table.add_column("标题", width=40)
        table.add_column("作者", width=12)
        table.add_column("链接", width=30)

        for r in items:
            type_icon = {"视频": "🎬", "图片": "🖼️", "图文": "📷"}.get(r.content_type, "📝")
            title = r.title[:40] or "-"
            author = r.author[:12] or "-"
            url = r.url[:30] or "-"
            table.add_row(type_icon, title, author, url)

        console.print(table)
        console.print("")


async def main_async(args):
    config = load_config()
    platforms = args.platforms if args.platforms else config.get("search", {}).get("platforms")

    console.print(f"\n[bold]🔍 搜索关键词：[/bold] [yellow]{args.keyword}[/yellow]")
    console.print(f"[dim]平台: {', '.join(platforms) if platforms else '全部'}[/dim]\n")

    # 执行搜索
    results = await search_all(
        keyword=args.keyword,
        platforms=platforms,
        limit=args.limit,
        config=config,
    )

    # 终端展示
    print_results(results)

    # 发送通知
    if args.notify:
        webhook = config.get("webhook", {})
        notify_map = {"feishu": webhook.get("feishu"), "wecom": webhook.get("wecom")}

        for notify_type in args.notify:
            url = notify_map.get(notify_type)
            if not url:
                console.print(f"[yellow]⚠️ {notify_type} webhook 未配置，请编辑 config.json[/yellow]")
                continue

            ok = await send_notification(results, args.keyword, config)
            if ok:
                console.print(f"[green]✅ {notify_type} 推送成功[/green]")
            else:
                console.print(f"[red]❌ {notify_type} 推送失败[/red]")

    # 导出 JSON
    if args.output:
        from models import SearchResult
        data = [
            {
                "title": r.title,
                "content": r.content,
                "url": r.url,
                "platform": r.platform,
                "author": r.author,
                "content_type": r.content_type,
                "time": r.time,
            }
            for r in results
        ]
        Path(args.output).write_text(json.dumps(data, ensure_ascii=False, indent=2))
        console.print(f"[green]💾 结果已保存到 {args.output}[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="中文多平台关键词搜索聚合工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py "AI大模型"                          # 搜索全部平台
  python main.py "AI大模型" --platforms baidu weibo  # 只搜索百度和微博
  python main.py "AI大模型" --notify feishu          # 搜索并推送到飞书
  python main.py "AI大模型" --output results.json    # 保存结果到文件
        """,
    )
    parser.add_argument("keyword", help="搜索关键词")
    parser.add_argument(
        "--platforms",
        nargs="+",
        help="指定搜索平台 (baidu weibo toutiao zhihu sohu douyin kuaishou xhs shipinhao)",
    )
    parser.add_argument("--limit", type=int, default=10, help="每个平台返回结果数 (默认: 10)")
    parser.add_argument(
        "--notify",
        nargs="+",
        choices=["feishu", "wecom"],
        help="推送通知到飞书/企业微信",
    )
    parser.add_argument("--output", "-o", help="保存结果到 JSON 文件")

    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
