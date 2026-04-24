# codex_queue_runner 使用说明

这个脚本做的是：
- 把 Codex 任务排队
- 一次只跑一个
- 如果检测到额度/频率限制或认证失败，就自动暂停队列
- 暂停时给指定邮箱发提醒
- 之后由你手动恢复，再继续跑

脚本路径：
- `scripts/codex_queue_runner.py`

默认状态目录：
- `~/.hermes/codex_queue/`

默认状态文件：
- `~/.hermes/codex_queue/state.json`

默认日志目录：
- `~/.hermes/codex_queue/logs/`

## 一、先设置提醒邮箱

```bash
python scripts/codex_queue_runner.py set-email zou.li@trs.com.cn
```

也可以临时覆盖：

```bash
python scripts/codex_queue_runner.py run-next --notify-email zou.li@trs.com.cn
```

## 二、添加任务

```bash
python scripts/codex_queue_runner.py add "codex exec 'fix bug in auth module'" --workdir /path/to/repo --name "修 auth bug"
```

如果任务运行需要额外环境变量：

```bash
python scripts/codex_queue_runner.py add "codex exec 'run tests'" \
  --workdir /path/to/repo \
  --env FOO=bar \
  --env BAZ=qux
```

## 三、执行下一个任务

```bash
python scripts/codex_queue_runner.py run-next
```

如果遇到以下情况，队列会自动暂停：
- quota 用完
- rate limit
- 认证失败

暂停后会把原因写进状态文件，并尝试发邮件。

## 四、查看状态

```bash
python scripts/codex_queue_runner.py status
```

## 五、恢复队列

```bash
python scripts/codex_queue_runner.py resume --clear-paused-tasks
```

说明：
- `resume`：解除全局暂停
- `--clear-paused-tasks`：把被暂停的任务重新放回 `queued`

## 六、重试某个任务

```bash
python scripts/codex_queue_runner.py retry <task_id>
```

它会复制一份历史任务重新入队，用新的 task_id。

## 七、邮件提醒前提

脚本现在优先走现成 QQ 发件脚本：
- `/root/.openclaw.pre-migration/workspace/mail/send_qq.py`
- `~/.config/openclaw-mail/qq_smtp.json`
- `~/.config/openclaw-mail/qq_smtp.pass`

如果这三样都在，提醒邮件会优先走 QQ SMTP 脚本发送。

兜底方式才是通用 SMTP 环境变量：
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`（可选，默认 587）

如果两套都不可用，脚本仍会暂停队列，但邮件会发不出去。

## 八、建议运行方式

最简单的方式是用 cron 或循环调度，每次只跑一个：

```bash
*/5 * * * * cd /root/.hermes/hermes-agent && /usr/bin/python3 scripts/codex_queue_runner.py run-next >> ~/.hermes/codex_queue/runner.log 2>&1
```

这样每 5 分钟尝试跑一个任务；一旦检测到额度/认证问题，就自动暂停，不会继续往后撞。

## 九、当前行为边界

这个脚本不会：
- 自动切换账号
- 自动规避额度限制
- 自动帮你重新登录

它只做合规版控制：
- 失败暂停
- 等你恢复
- 给你提醒
