# Clay onboarding

Clay should install from the fork inside WSL2 or native POSIX shell, never native Windows.

```bash
mkdir -p $HOME/repos
cd $HOME/repos
git clone https://github.com/ptanner66-prog/hermes-agent.git
cd hermes-agent
./setup-hermes.sh
source venv/bin/activate
./hermes setup
cp config/models.yml.example config/models.yml
bash scripts/apply-models-yml.sh
./hermes doctor
```

Clay-specific legal-domain review work routes through `legal-tech-reviewer` and the rules in `.claude/rules/legal-tech-coding.md`. Items Clay must decide go to `OPERATOR-INBOX/clay/` and must cite one of the admission criteria in `OPERATOR-INBOX/README.md`.
