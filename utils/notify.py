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

    text = "\n".join(lines)
    # 飞书有 30720 字节限制，在换行处截断防止文字乱掉
    if len(text) > 3000:
        text = text[:3000]
        cut = text.rfind("\n")
        if cut > 0:
            text = text[:cut] + "\n\n... 内容已截断"
    return text


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


async def check_webhook(config: dict, webhook_types: list[str] | None = None) -> dict[str, bool]:
    """检查 webhook 连通性，发送测试消息

    Args:
        config: 配置字典
        webhook_types: 要检查的 webhook 类型列表，None 表示检查所有已配置的

    Returns:
        {类型: 是否成功} 的字典
    """
    webhook = config.get("webhook", {})
    if webhook_types is None:
        webhook_types = [k for k, v in webhook.items() if v]

    test_msg_feishu = {
        "msg_type": "text",
        "content": {
            "text": "🔧 China-Platform-Search 连接测试 ✅\n如果你看到这条消息，说明 webhook 配置正确。"
        }
    }
    test_msg_wecom = {
        "msgtype": "text",
        "text": {
            "content": "🔧 China-Platform-Search 连接测试 ✅\n如果你看到这条消息，说明 webhook 配置正确。"
        }
    }

    results = {}
    for notify_type in webhook_types:
        url = webhook.get(notify_type)
        if not url:
            print(f"  ⚠️ {notify_type}: webhook 未配置")
            results[notify_type] = False
            continue

        payload = test_msg_feishu if notify_type == "feishu" else test_msg_wecom
        ok = run_curl(url, payload)
        icon = "✅" if ok else "❌"
        print(f"  {icon} {notify_type}: {'连接成功' if ok else '连接失败'}")
        results[notify_type] = ok

    return results


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
