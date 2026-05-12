# Community announcements — supply-chain advisory

These are the canonical short-form posts to drop in Discord, Telegram,
the GitHub README banner, and the pinned issue. Use them verbatim or
edit to taste — the technical details and remediation steps are
in `website/docs/community/security-advisories/shai-hulud-mistralai-2026-05.md`.

---

## Discord / Telegram (short-form, ~280 chars)

```
SECURITY ADVISORY: The Mini Shai-Hulud worm hit PyPI today and
poisoned mistralai 2.4.6 — the Mistral AI Python SDK. If you ran a
fresh `hermes install` between roughly 2026-05-11 and 2026-05-12, you
may have it.

→ Run `hermes doctor` to check.
→ If flagged: pip uninstall mistralai, rotate all keys in
  ~/.hermes/.env, audit ~/.npmrc / ~/.aws/credentials / GitHub PATs.
→ We've disabled Mistral TTS/STT and removed it from `[all]` until
  PyPI restores a clean release.

Full details: <link to docs page>
```

---

## GitHub pinned issue title + body

**Title:** `Security advisory: mistralai 2.4.6 supply-chain compromise (Mini Shai-Hulud)`

**Body:**

> The PyPI `mistralai` package was compromised on 2026-05-12 with a
> credential-stealing worm (Mini Shai-Hulud). If you installed Hermes
> with `[all]` extras between the upload and PyPI's quarantine, you
> may have `mistralai 2.4.6` in your venv.
>
> **Action required for affected users:**
> 1. Run `hermes doctor` — if `mistralai==2.4.6` is flagged, you're affected
> 2. `pip uninstall mistralai`
> 3. Rotate every API key in `~/.hermes/.env`
> 4. Audit `~/.npmrc`, `~/.pypirc`, `~/.aws/credentials`, GitHub PATs
> 5. `hermes doctor --ack shai-hulud-2026-05` to dismiss the warning
>
> **What we've shipped:**
> - Mistral TTS / STT disabled in Hermes runtime (PR #24205)
> - `mistral` removed from `[all]` extra so fresh installs don't pull it
> - `hermes doctor` now detects the compromised version and prints
>   remediation steps
> - Installer fallback tiers hardened — one quarantined upstream
>   package no longer silently demotes users to a stripped install
> - Lazy-install framework so future opt-in backends install on demand
>   (smaller blast radius for the next supply-chain incident)
>
> Full advisory: <docs link>
> Socket report: <https://socket.dev/blog/mini-shai-hulud-worm-pypi>
> PyPI status: quarantined

---

## README top banner (until ~2026-06-12)

```markdown
> ⚠ **Security advisory (2026-05-12):** The PyPI `mistralai` package
> was compromised. If you installed Hermes with `[all]` extras during
> the affected window, run `hermes doctor` to check whether you have
> the poisoned version. [Full advisory and remediation
> steps.](website/docs/community/security-advisories/shai-hulud-mistralai-2026-05.md)
```

---

## Email / mailing list (long-form)

Same content as the docs page — link to the published docs URL once
the website rebuilds:
<https://hermes-agent.nousresearch.com/docs/community/security-advisories/shai-hulud-mistralai-2026-05>
