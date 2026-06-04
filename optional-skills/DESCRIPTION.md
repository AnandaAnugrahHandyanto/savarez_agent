# Optional Skills

Official skills maintained by Ananda Anugrah Handyanto that are **not activated by default**.

These skills ship with the savarez-agent repository but are not copied to
`~/.savarez/skills/` during setup. They are discoverable via the Skills Hub:

```bash
savarez skills browse               # browse all skills, official shown first
savarez skills browse --source official  # browse only official optional skills
savarez skills search <query>       # finds optional skills labeled "official"
savarez skills install <identifier> # copies to ~/.savarez/skills/ and activates
```

## Why optional?

Some skills are useful but not broadly needed by every user:

- **Niche integrations** — specific paid services, specialized tools
- **Experimental features** — promising but not yet proven
- **Heavyweight dependencies** — require significant setup (API keys, installs)

By keeping them optional, we keep the default skill set lean while still
providing curated, tested, official skills for users who want them.
