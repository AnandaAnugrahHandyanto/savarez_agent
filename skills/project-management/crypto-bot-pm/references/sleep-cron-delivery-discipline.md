# Sleep Cron Delivery Discipline

Use this when running unattended `crypto_bot` PM/autonomy work as a scheduled Hermes cron job.

## Durable lesson

Cron jobs already deliver the agent's final response to the configured destination. During a cron-run session, do **not** call `send_message` or otherwise manually deliver the milestone report unless the cron prompt explicitly asks for a different external delivery target.

## Reporting pattern

- Put the full milestone/status report in the final assistant response.
- If the prompt says silent success is allowed and there is genuinely nothing new, return exactly `[SILENT]` and nothing else.
- Never combine `[SILENT]` with other content.
- Use `send_message` only if the user explicitly asks for an additional out-of-band delivery target outside the cron job's configured delivery.

## Why this matters

Manual delivery from inside a cron job can duplicate updates, bypass the scheduler's delivery framing, and create noisy sleep-window reports. The scheduler is the delivery mechanism; the agent's job is to produce the final content only.
