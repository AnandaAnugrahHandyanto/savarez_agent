---
name: ai-provider-budget-advice
description: Advise budget-conscious users choosing AI subscriptions, API credits, student/free plans, and Hermes-compatible provider spend.
version: 1.0.0
author: Mizuki
license: MIT
metadata:
  hermes:
    tags: [ai, subscriptions, providers, budget, openrouter, gemini, copilot, hermes]
---

# AI Provider Budget Advice

Use this when the user asks what AI subscription, API credit, promo, or model/provider to buy — especially with a small monthly budget or when they want to power Hermes/Mizuki.

## Core distinction

First separate the purchase into two categories:

1. **App subscription** — ChatGPT, Claude Pro, Google AI Pro, Perplexity, etc. Good for using that company's web/mobile/workspace tools.
2. **API/model credit** — OpenRouter, provider API keys, AI Studio API billing, etc. Good for powering Hermes/agents directly.

For Hermes-specific value, API credit usually beats an app subscription because Hermes can route tool-using agent calls through it. For personal app features, a subscription can be better.

## Company/team purchase pattern

When the AI is being bought by a company for employee/manager work, do **not** optimize only for model quality or cheapest price. Start with business safety and workflow fit:

1. **Use business/team plans, not personal/free accounts, for company data.** Warn against pasting sensitive company data into random free AI tools or browser extensions.
2. **Choose by the company's existing productivity stack:**
   - Microsoft 365 / Excel / Outlook / Teams heavy → **Microsoft Copilot for Microsoft 365** is usually the best first fit.
   - Google Workspace / Gmail / Drive / Sheets heavy → **Gemini for Google Workspace** is usually the best first fit.
   - Mixed workflows, uploaded files, planning, reporting, and general reasoning → **ChatGPT Team/Business** is the flexible default.
   - Long policies/contracts/reports and careful writing → **Claude Team** is strong.
3. **Recommend a small pilot before rollout.** For a manager/team scenario, suggest 3–5 pilot users across the workflow, measure time saved, output quality, adoption, and data-safety fit before buying seats for everyone.
4. **Frame it as workflow acceleration, not staff replacement.** Especially when automation could reduce manual work, recommend language like “help the team finish boring work faster and focus on exceptions.”

## Recommended decision flow

1. **Ask/Infer the goal, not the brand.**
   - "Make Hermes/Mizuki stronger" → prefer API credit.
   - "Use Gemini/ChatGPT/Claude app personally" → subscription may fit.
   - "Coding in VS Code" → check GitHub Copilot/free student options.
   - "Study PDFs/notes/research" → Google AI Pro/NotebookLM or Perplexity can be strong.

2. **Check free/student promos before paid spend.**
   - For students, check GitHub Student Developer Pack and Copilot student benefits.
   - Check provider student pages/promos live; these change often.

3. **For a small budget such as ~$10/month:**
   - If powering Hermes: recommend OpenRouter/API credit as the default.
   - If the user will heavily use Google ecosystem tools: Google AI Pro can be worth it, especially when discounted.
   - Avoid recommending $20+ subscriptions unless the user's use case clearly exceeds what API credit/free tiers provide.

4. **Give a budget-preserving model strategy.**
   - Cheap/default model for daily chat and study.
   - Strong/expensive model only for hard debugging, DevOps, repo work, architecture, or deep explanations.
   - Explain that agent/tool usage burns more tokens because context, file contents, and tool outputs are included.

5. **Be explicit about limits.**
   - App subscription benefits do not automatically equal API access for Hermes.
   - "AI Studio higher limits" may help building/prototyping, but verify whether it grants the API access/billing path Hermes needs.
   - Pricing and promos change; verify current pages before hard claims.

## Practical default recommendations

- **Pure Hermes/agent value with small paid budget:** OpenRouter credit.
- **Pure Hermes/agent value with $0 budget:** Check **Nous Portal Free** first. If already logged in, verify with `hermes portal status`, then test a current free model with `hermes chat -Q --provider nous -m '<free-model-id>' -q 'Reply with exactly: OK'`. Free model IDs change, so use Portal's recommended/free model list rather than assuming old names.
- **Google app + NotebookLM + Drive/storage + Gemini app:** Google AI Pro.
- **VS Code coding for a student:** GitHub Student Developer Pack/Copilot Student first, then paid options.
- **Research/search app:** Perplexity only if the user specifically wants that workflow.
- **Claude app:** excellent, but usually more expensive than a $10 budget.

## Nous Portal free-tier workflow for Hermes

Use this when the user asks for free AI inside Hermes/Mizuki or specifically mentions Nous Portal.

1. Inspect the local Portal state:
   - `hermes portal status`
   - Look for `Auth: ✓ logged in`, current provider/model, and Tool Gateway routing.
2. Check the live Portal plan page or recommended-model endpoint when possible; free models and paid plan features change.
3. Prefer a real smoke test over advice-only:
   - `hermes chat -Q --provider nous -m '<free-model-id>' -q 'Reply with exactly: NOUS_FREE_MODEL_OK'`
4. Explain the practical distinction:
   - Free tier can provide free model access.
   - Paid Portal tiers may include hosted Tool Gateway usage and monthly credits.
   - A Hermes config can be logged into Nous Portal while still using another default provider; do not assume login means active routing.
5. If the user wants to switch permanently, use `hermes model` or set provider/model explicitly; for one-off use, pass `--provider nous -m <model>`.

Reference: `references/nous-portal-free-tier-hermes.md`.

## Communication style for budget advice

- Keep it direct and comparative.
- Use tables sparingly when they clarify the decision.
- Do not overhype promos; identify the catch.
- For the user Hevar, favor practical monthly value and Hermes compatibility over brand prestige.

## References

- `references/ai-promos-and-budgeting-2026-05.md` — session-derived notes on Google AI Pro promo, OpenRouter credit fit, Copilot student/free signals, and caveats.
