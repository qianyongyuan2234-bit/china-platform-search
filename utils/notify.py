"""通知模块 - 飞书/企业微信 webhook (使用 curl 直接调用,避免代理问题)"""
import json
import subprocess
from datetime import datetime
from models import SearchResult


def run_curl(webhook_url: str, payload: dict) -> bool:
    """用 curl 发送 webhook 请求"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-w", "\n%{http_code}", "-X", "POST",
             webhook_url, "-H", "Content-Type: application/json",
             "-d", json.dumps(payload)],
            capture_output=True, text=True, timeout=15
        )
        status_code = int(result.stdout.strip().split("\n")[-1])
        body = result.stdout.rsplit("\n", 1)[0]
        print(f"  Webhook 响应: {body} (HTTP {status_code})")
        return status_code == 200
    except Exception as e:
        print(f"  ❌ curl 发送失败: {e}")
        return False


def format_feishu_message(results: list[SearchResult], keyword: str) -> str:
    """格式化飞书消息 - 每条包含标题+链接+摘要"""
    lines = []
    lines.append(f"🔍 搜索「{keyword}」")
    lines.append(f"📊 共 {len(results)} 条 | {datetime.now().strftime('%H:%M')}")
    lines.append("")

    # 按平台分组
    platform_groups = {}
    for r in results:
        if r.platform not in platform_groups:
            platform_groups[r.platform] = []
        platform_groups[r.platform].append(r)

    for platform, items in platform_groups.items():
        lines.append(f"━━ {platform} ({len(items)}条) ━━")

        for i, r in enumerate(items[:8], 1):
            type_icon = {"视频": "🎬", "图片": "🖼️", "图文": "📷"}.get(r.content_type, "📝")
            # 标题
            lines.append(f"{i}. {type_icon} {r.title}")
            # 链接 - 必显
            if r.url and r.url not in ("javascript:void(0);", ""):
                lines.append(f"   🔗 {r.url}")
            # 摘要 - 有内容就显示
            if r.content and r.content != r.title:
                summary = r.content[:80]
                if len(r.content) > 80:
                    summary += "..."
                lines.append(f"   💬 {summary}")
            # 作者
            if r.author:
                lines.append(f"   👤 {r.author}")
            lines.append("")

        lines.append("")

    return "\n".join(lines)[:3000]


async def send_feishu(webhook_url: str, results: list[SearchResult], keyword: str):
    if not webhook_url:
        return False

    text = format_feishu_message(results, keyword)

    msg = {
        "msg_type": "text",
        "content": {
            "text": text
        }
    }

    return run_curl(webhook_url, msg)


async def send_wecom(webhook_url: str, results: list[SearchResult], keyword: str):
    if not webhook_url:
        return False

    text = format_feishu_message(results, keyword)

    msg = {
        "msgtype": "text",
        "text": {
            "content": text
        }
    }

    return run_curl(webhook_url, msg)


async def send_notification(results: list[SearchResult], keyword: str, config: dict):
    webhook = config.get("webhook", {})
    success = False

    if webhook.get("feishu"):
        ok = await send_feishu(webhook["feishu"], results, keyword)
        print(f"飞书推送: {'✅ 成功' if ok else '❌ 失败'}")
        success = success or ok

    if webhook.get("wecom"):
        ok = await send_wecom(webhook["wecom"], results, keyword)
        print(f"企业微信推送: {'✅ 成功' if ok else '❌ 失败'}")
        success = success or ok

    return success
