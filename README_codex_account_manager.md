# Codex Account Manager

一个面向 Hermes/Codex OAuth 的多账号管理工具。

功能：
- 多个 Codex 账号登录与保存
- 添加账号后尽量直接展示账号邮箱；`list` / `probe` / 提醒邮件里优先显示邮箱
- `list` 默认刷新当前活动账号快照；`list --refresh-all` 可一次刷新全部账号额度快照
- `probe` / `watch` 定时探测全部账号是否还能继续使用
- `switch` 一键切换当前活动账号
- `probe --auto-switch` 在当前账号失效/限额时自动切换到下一个健康账号
- `run --command ...` 包装 Codex 命令，检测到额度/认证失败后自动切号重试
- `doctor` 检查账号池 / Hermes auth / Codex CLI auth 是否一致
- `doctor --fix` 发现漂移时按当前活动账号一键修正登录态
- 账号认证失效时自动发邮件提醒，并带上具体账号邮箱/标识
- 支持 Plus / Team 账号到期前 3 天内发邮件提醒

入口：
- 安装后命令：`codex-account-manager`
- 直接运行：`python codex_account_manager.py`

## 常用命令

```bash
codex-account-manager add --activate
codex-account-manager add --plan-expires-at 2026-05-01T00:00:00Z --notify-email zou.li@trs.com.cn
codex-account-manager list
codex-account-manager list --refresh-all
codex-account-manager switch li@example.com
codex-account-manager probe --auto-switch --notify-email zou.li@trs.com.cn
codex-account-manager doctor
codex-account-manager doctor --fix
codex-account-manager watch --interval 1800 --auto-switch --notify-email zou.li@trs.com.cn
codex-account-manager run --command "codex exec 'fix auth bug'" --notify-email zou.li@trs.com.cn
```

如果你是在 Hermes CLI 里用，也可以直接这样：

```text
/codex list
/codex list --refresh-all
/codex switch li@example.com
/codex probe --auto-switch
/codex doctor
/codex doctor --fix
```

## 邮件提醒

优先使用现成 QQ 发件脚本：
- `/root/.openclaw.pre-migration/workspace/mail/send_qq.py`
- `~/.config/openclaw-mail/qq_smtp.json`
- `~/.config/openclaw-mail/qq_smtp.pass`

如果没有，再回退到 SMTP 环境变量：
- `EMAIL_ADDRESS`
- `EMAIL_PASSWORD`
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`（可选，默认 587）

也可以直接设置默认提醒邮箱：

```bash
export CODEX_MANAGER_NOTIFY_EMAIL="zou.li@trs.com.cn"
```

说明：
- 认证失效 / refresh token 失效 / 额度耗尽提醒邮件会带上具体账号邮箱与账号标识
- Plus / Team 到期提醒默认看每个账号保存的 `plan_expires_at`
- 可在 `add` 时通过 `--plan-expires-at` 记录到期时间，也可后续手动维护配置

## 定时巡检示例

```bash
*/30 * * * * cd /root/.hermes/hermes-agent && /root/.hermes/hermes-agent/venv/bin/python codex_account_manager.py probe --auto-switch --notify-email zou.li@trs.com.cn >> /tmp/codex-account-manager.log 2>&1
```

当前机器上已经落了一条 30 分钟巡检 cron，实际日志路径是：

```bash
/root/.hermes/codex_account_manager/probe.log
```

推荐排障顺序：
1. `codex-account-manager list --refresh-all` 看所有账号实时快照
2. `codex-account-manager doctor` 看账号池 / Hermes / Codex CLI 是否一致
3. 如果 doctor 报漂移，直接跑 `codex-account-manager doctor --fix`
4. 再用 `codex login status` 和 `codex exec ...` 做一次 CLI 实测

## 说明

Codex 目前没有公开、稳定的“剩余额度数字”接口。
所以这里的“额度查询”实际上是：
1. 先刷新 token
2. 再查询 `https://chatgpt.com/backend-api/wham/usage` 的使用状态
3. 根据真实返回判断账号是可用、频率限制、额度耗尽还是认证失效

这样虽然拿不到具体数值，但对“还能不能继续跑”和“该不该切号”更实用。
另外，`probe` 之前遇到的 HTTP 400 不是因为没走系统代理，而是因为旧的 `/responses` 探测请求缺少 `stream=true`；现在已改成 usage 接口，且会默认读取 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`。
