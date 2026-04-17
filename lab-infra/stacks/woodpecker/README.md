## Woodpecker CI — README

### Setup for a new project repo

1. Go to `woodpecker.jaxmind.xyz`
2. Activate the repo
3. Add a `.woodpecker.yml` to the repo root (template below)
4. Push to main → auto deploy

---

### .woodpecker.yml template (copy to project repo)

```yaml
when:
  branch: main
  event: push

steps:
  - name: deploy
    image: docker/compose:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - /lab/stacks/${CI_REPO_NAME}:/app
    commands:
      - cd /app
      - docker compose pull
      - docker compose up -d --remove-orphans
      - docker image prune -f
```

### Secrets

Set secrets in Woodpecker UI → repo settings → secrets.
Reference in pipeline as `$SECRET_NAME`.
