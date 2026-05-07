import json

from gateway.todo_replies import apply_structured_todo_reply, looks_like_structured_todo_reply, parse_structured_todo_reply


def test_parse_structured_todo_reply_supports_multiple_lines_and_semicolons():
    directives = parse_structured_todo_reply("add: write tests; ship fix\ndoing: review cron\nignore this")

    assert [(item.action, item.title) for item in directives] == [
        ("add", "write tests"),
        ("add", "ship fix"),
        ("doing", "review cron"),
    ]


def test_looks_like_structured_todo_reply_requires_reply_format_context():
    assert looks_like_structured_todo_reply("add: ship it", "Reply format\nadd: ...\ndoing: ...") is True
    assert looks_like_structured_todo_reply("add: ship it", None) is False
    assert looks_like_structured_todo_reply("hello", "Reply format\nadd: ...") is False


def test_apply_structured_todo_reply_updates_json_file(tmp_path):
    tasks_path = tmp_path / "tasks.json"
    tasks_path.write_text(
        json.dumps(
            {
                "version": 1,
                "created": "2026-04-14",
                "updated": "2026-04-14",
                "tasks": [
                    {"title": "file taxes", "status": "todo", "notes": ""},
                    {"title": "call doctor", "status": "blocked", "notes": ""},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = apply_structured_todo_reply(
        tasks_path,
        parse_structured_todo_reply("doing: file taxes\ndone: call doctor\nadd: pick up meds"),
    )

    saved = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert [task["status"] for task in saved["tasks"]] == ["doing", "done", "todo"]
    assert [task["title"] for task in saved["tasks"]] == ["file taxes", "call doctor", "pick up meds"]
    assert result.changes == [
        "todo -> doing: file taxes",
        "blocked -> done: call doctor",
        "added: pick up meds",
    ]
    assert [task["title"] for task in result.open_tasks] == ["file taxes", "pick up meds"]
