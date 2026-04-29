# Rule: rl-training

Paths: `environments/`, `batch_runner.py`, `rl_cli.py`, `mini_swe_runner.py`, `trajectory_compressor.py`, `tinker-atropos`.

DO NOT:
- Never push trajectory data with privileged or PII content.
- Never run RL training on a production-gateway VM.
- Trajectory compression is destructive.

Architecture Notes: RL surfaces are optional and isolated from daily coding-agent runtime.

Thresholds: training changes need targeted tests and data-scrub review.

Key Files: `batch_runner.py`, `trajectory_compressor.py`, `environments/`.
