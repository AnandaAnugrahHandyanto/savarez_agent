# Social comment insight pipeline

`scripts/social_comment_pipeline.py` turns user-authorized social-platform comment exports into product insight archives and Hermes Kanban task packages.

## Scope and compliance

Use only data you are allowed to process:

- Official platform APIs or export files.
- Creator/admin dashboard exports.
- User-provided CSV/JSON/JSONL comment dumps.

Do **not** use this pipeline to bypass logins, CAPTCHA, anti-bot protections, rate limits, paywalls, or platform terms. The script deliberately starts from local export files instead of scraping protected pages.

## Input formats

The pipeline accepts `.json`, `.jsonl`, and `.csv`. It recognizes common fields:

- comment text: `text`, `content`, `comment`, `body`, `message`, `评论`, `内容`
- IDs: `id`, `comment_id`, `post_id`, `video_id`, `note_id`, etc.
- metadata: `platform`, `author`, `created_at`, `url`

Minimal JSONL example:

```jsonl
{"platform":"douyin","post_id":"p1","id":"c1","text":"希望支持导出 Excel 报表，手工统计太麻烦了"}
{"platform":"xiaohongshu","post_id":"n1","id":"c2","text":"登录验证码经常失败，账号打不开"}
```

## One-shot analysis

```bash
python scripts/social_comment_pipeline.py \
  --input ~/.hermes/social-comments/inbox \
  --output ~/.hermes/social-comments/archive \
  --dry-run-kanban
```

Outputs per run:

- `normalized_comments.jsonl`: normalized/deduplicated comments.
- `insights.json`: structured insights.
- `insights.md`: readable product insight report.
- `product_manager_brief.md`: archive package for the product-manager agent.
- `agent_tasks/*.md`: task package for product manager, developer, tester, and acceptance agents.
- `kanban_tasks.json`: structured task payloads.
- `kanban_dispatch_results.json`: dry-run commands or actual Hermes Kanban create results.
- `summary.json`: run summary.

## Dispatch to Hermes Kanban

Dry run first:

```bash
python scripts/social_comment_pipeline.py \
  --input ~/.hermes/social-comments/inbox/comments.jsonl \
  --dry-run-kanban
```

Create Kanban cards:

```bash
python scripts/social_comment_pipeline.py \
  --input ~/.hermes/social-comments/inbox/comments.jsonl \
  --dispatch-kanban \
  --workspace scratch
```

Each top requirement becomes four role-specific cards:

- `product_manager`: clarify and prioritize requirement.
- `developer`: implement MVP or technical fix.
- `tester`: design and run tests.
- `acceptance`: verify against acceptance criteria.

Use `--board <slug>` if you maintain a dedicated board.

## Scheduled directory watcher

`scripts/social_comment_watch.py` scans an inbox directory, processes new files once, and stays silent when there is nothing new. This is suitable for Hermes cron `--no-agent` jobs.

Manual run:

```bash
python scripts/social_comment_watch.py \
  --input-dir ~/.hermes/social-comments/inbox \
  --output ~/.hermes/social-comments/archive \
  --dry-run-kanban
```

Cron job example:

```bash
hermes cron create "*/30 * * * *" \
  --name social-comment-watch \
  --script social_comment_watch.py \
  --no-agent
```

When ready to create tasks automatically, pass script args through your cron wrapper or run a wrapper script that adds `--dispatch-kanban`.

## Product workflow

1. Put authorized export files into `~/.hermes/social-comments/inbox/`.
2. Watcher runs by cron and archives a report under `~/.hermes/social-comments/archive/`.
3. Product manager agent reads `product_manager_brief.md` and generated task files.
4. Optional Kanban dispatch creates subagent cards for PM/developer/tester/acceptance.
5. Acceptance agent verifies against the generated criteria before release.
