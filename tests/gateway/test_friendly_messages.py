"""Regression tests for gateway friendly-message contracts."""

from gateway.friendly_messages import (
    parse_approval_reply,
    render_ack,
    render_capabilities,
    render_background_failure,
    render_background_result,
    render_approval_request,
    render_busy_ack,
    render_digest_report,
    render_greeting,
    render_inactivity_timeout,
    render_persona_reply,
    render_simple_done,
    render_simple_failure,
    render_starting,
    render_plain_table,
    render_task_progress,
    render_update_result,
    render_welcome,
)


def test_approval_request_uses_friendly_template():
    text = render_approval_request(
        "python3 -c \"print('hello')\"",
        "agent:main:weixin:dm:wxid_user",
        "script execution via -e/-c flag",
    )

    assert "命令需要审批" in text
    assert "执行临时代码片段" in text
    assert "【可选操作】" in text
    assert "01｜批准本次" in text
    assert "03｜永久允许" in text
    assert "Dangerous command requires approval" not in text
    assert "script execution via" not in text


def test_welcome_and_capabilities_use_persona_name():
    cfg = {"friendly": {"persona": {"display_name": "小舟"}}}

    welcome = render_welcome(cfg)
    capabilities = render_capabilities(cfg)

    assert "我是「小舟」，你的随身执行伙伴 😊～" in welcome
    assert "我是「小舟」，我可以帮你做这些 😊～" in capabilities
    assert "AI 助手" not in welcome
    assert "Hermes Agent" not in welcome
    assert "查天气" in capabilities
    assert "固定格式" in capabilities
    assert "✨" in welcome
    assert "✨" in capabilities


def test_light_chat_templates_are_warm_friendly():
    cfg = {"friendly": {"persona": {"display_name": "贾维斯"}}}

    greeting = render_greeting(cfg)
    ack = render_ack(cfg)
    starting = render_starting("先看一下当前状态", cfg)
    done = render_simple_done()
    failure = render_simple_failure("RuntimeError: Traceback boom")

    assert "我在，贾维斯在线 😊～" in greeting
    assert "告诉我就行 ✨" in greeting
    assert ack == "收到，贾维斯来处理 😊"
    assert starting == "我来处理，先看一下当前状态 🔎"
    assert "处理好了 🌿" in done
    assert "这轮没跑完 ⚠️" in failure
    assert "RuntimeError" not in failure
    assert "Traceback" not in failure


def test_persona_reply_handles_identity_and_capability_queries():
    cfg = {"friendly": {"persona": {"display_name": "小舟"}}}

    assert "小舟在线" in render_persona_reply("你好", cfg)
    assert "小舟在线" in render_persona_reply("小舟", cfg)
    assert "我是「小舟」" in render_persona_reply("你是谁？", cfg)
    assert "我可以帮你做这些" in render_persona_reply("你能干嘛", cfg)
    assert render_persona_reply("帮我查天气", cfg) is None


def test_digest_report_uses_plain_divider_not_markdown_table():
    table = render_plain_table(
        ["时间", "任务", "状态"],
        [["22:00", "每周 Cron 治理复盘", "待运行/待发送"]],
    )
    report = render_digest_report(
        "⚠️ 当前处理受阻",
        headline="🕙 截至 2026-05-17 21:24，今天还没发的只剩 1 个明确任务",
        sections=[
            {
                "title": "📌 今晚还未到点",
                "headers": ["时间", "任务", "状态"],
                "rows": [["22:00", "每周 Cron 治理复盘", "待运行/待发送"]],
            },
            {
                "title": "🟢 刚才已补上/已运行",
                "bullets": ["Cron Guard：21:20 ok"],
            },
        ],
        next_step="你现在不用处理；如果要补跑，直接告诉我。",
    )

    assert "────────────────────────────────────────" in table
    assert "────────────────────────────────────────" in report
    assert "|---|" not in report
    assert "| 时间 |" not in report
    assert "🧭 下一步" in report
    assert "Cron Guard：21:20 ok" in report


def test_background_and_update_results_use_friendly_cards():
    background = render_background_result("整理今日任务", "已完成整理。")
    failure = render_background_failure("task-1", "RuntimeError: Traceback boom")
    update_ok = render_update_result(True)
    update_fail = render_update_result(False, "HTTP 502 ret=-2", exit_code=1)

    assert "🌿 后台任务已完成" in background
    assert "任务｜整理今日任务" in background
    assert "⚠️ 后台任务没跑完｜task-1" in failure
    assert "RuntimeError" not in failure
    assert "Traceback" not in failure
    assert "🌿 Hermes 更新已完成" in update_ok
    assert "⚠️ Hermes 更新没完成" in update_fail
    assert "HTTP 502" not in update_fail
    assert "ret=-2" not in update_fail
    assert "Background task complete" not in background
    assert "Hermes update finished" not in update_ok


def test_parse_approval_reply_accepts_explicit_friendly_choices():
    assert parse_approval_reply("01｜批准本次") == "once"
    assert parse_approval_reply("本会话允许") == "session"
    assert parse_approval_reply("永久允许") == "always"
    assert parse_approval_reply("04 拒绝") == "deny"
    assert parse_approval_reply("yes") is None
    assert parse_approval_reply("/approve always") is None


def test_progress_template_hides_internal_activity():
    text = render_task_progress(
        3,
        {
            "api_call_count": 16,
            "max_iterations": 90,
            "last_activity_desc": "receiving stream response",
            "current_tool": None,
        },
    )

    assert "任务仍在处理中" in text
    assert "正在等待模型输出" in text
    assert "iteration" not in text
    assert "16/90" not in text
    assert "receiving stream response" not in text


def test_busy_and_timeout_templates_hide_internal_activity():
    summary = {
        "api_call_count": 16,
        "max_iterations": 90,
        "last_activity_desc": "receiving stream response",
        "current_tool": None,
    }

    busy = render_busy_ack("queue", summary, elapsed_mins=2)
    timeout = render_inactivity_timeout(30, summary)

    for text in (busy, timeout):
        assert "【状态】" in text
        assert "iteration" not in text
        assert "16/90" not in text
        assert "receiving stream response" not in text
