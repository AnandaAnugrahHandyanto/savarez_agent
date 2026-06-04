# SkillOpt-style skill optimization

Hermes skills can now be promoted through a conservative validation gate inspired by:

> Yifan Yang, Ziyang Gong, Weiquan Huang, Qihao Yang, Ziwei Zhou, Zisu Huang, Yan Li, Xuemei Gao, Qi Dai, Bei Liu, Kai Qiu, Yuqing Yang, Dongdong Chen, Xue Yang, and Chong Luo. **“SkillOpt: Executive Strategy for Self-Evolving Agent Skills.”** arXiv:2605.23904, 2026. <https://arxiv.org/abs/2605.23904>

This is deliberately not a full research-system clone. It brings the useful operational spine into Hermes:

- keep candidate skill edits outside the live skill until they are evaluated;
- validate the candidate `SKILL.md` frontmatter/body before touching the current skill;
- optionally run a project-specific validator command;
- promote only when the candidate strictly improves a held-out score;
- write accepted promotions to `.skillopt/history.jsonl`;
- write failed candidates to `.skillopt/rejected.jsonl` so future optimizers can learn from bad edits;
- back up the previous `SKILL.md` before replacing it.

## CLI

```bash
hermes skills optimize path/to/my-skill \
  --candidate /tmp/candidate-SKILL.md \
  --baseline-score 0.72 \
  --candidate-score 0.81 \
  --validator 'python tests/evaluate_skill.py'
```

The validator runs in the skill directory and receives:

- `HERMES_SKILLOPT_SKILL` — current live `SKILL.md`
- `HERMES_SKILLOPT_CANDIDATE` — candidate `SKILL.md`

By default, equal scores are rejected. Use `--allow-equal` only when your evaluator is noisy and you want to permit ties. Use `--dry-run` to record the decision without replacing the skill.

## Files written

For a skill at `~/.hermes/skills/my-skill/SKILL.md`, optimization metadata lives beside the skill:

```text
~/.hermes/skills/my-skill/.skillopt/
├── backups/
│   └── SKILL.<timestamp>.<sha>.md
├── history.jsonl
└── rejected.jsonl
```

That keeps the live skill simple while preserving the audit trail needed for a future autonomous optimizer.
