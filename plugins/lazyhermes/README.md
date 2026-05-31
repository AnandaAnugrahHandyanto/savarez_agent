# lazyhermes

Hermes-native retrofit of the LazyCodex/OmO workflow ideas. The plugin keeps
the useful parts local to Hermes:

- `/ulw-plan` and `/ultrawork-plan` create durable plans in `plans/`, then forward a
  LazyCodex-style goal bootstrap to the Hermes agent instead of stopping at plan creation.
- `/ulw-loop` and `/ultrawork-loop` create run state under
  `.hermes/lazyhermes/runs/` and dispatch the task back to the Hermes agent.
- `/start-work` opens or dry-runs a plan against a workspace.
- The `pre_llm_call` hook injects an Ultrawork directive when the user says
  `ulw` or `ultrawork`. Direct `ulw <task>` prompts also include goal-tool
  instructions: call `get_goal` first, call `create_goal` only when needed, and
  reserve `update_goal` for verified completion or a real blocker.
- Explicit skills are available as `lazyhermes:ultrawork`, `lazyhermes:rules`,
  and `lazyhermes:lsp`.

Enable with:

```yaml
plugins:
  enabled:
    - lazyhermes
```

## Reference

Inspired by `code-yeongyu/lazycodex` and its bundled OmO plugin layout. This
port does not execute `bunx`, `omo`, or any external prompt-runtime installer.
