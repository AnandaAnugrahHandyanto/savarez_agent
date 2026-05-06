# Deploying Hermes to the Cloud (GitHub Actions)

While Hermes is designed for edge devices, it can be easily deployed as a cloud-based agent using GitHub Actions. This allows you to interact with Hermes directly through Issue comments or Pull Request descriptions.

## Prerequisites

1.  **API Keys:** You will need an API key for your preferred LLM provider (e.g., `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
2.  **GitHub Secrets:** Add your API keys to your GitHub repository secrets (`Settings > Secrets and variables > Actions`).

## Setup

The repository includes a pre-configured workflow in `.github/workflows/hermes-cloud.yml`.

### 1. Enable the Workflow
Once the workflow file is in your `.github/workflows` directory, GitHub will automatically detect it.

### 2. Interactions
You can trigger Hermes in three ways:
*   **Workflow Dispatch:** Go to the "Actions" tab, select "Hermes Cloud Integration", and click "Run workflow" with a custom query.
*   **Issue Comments:** Comment on any issue in the repository. Hermes will respond based on the comment body.
*   **New Issues:** Open a new issue. Hermes will process the issue description.

## How it Works

*   **Persistence:** Hermes state (including installed skills and memory) is persisted across runs using GitHub Actions caching. The state is stored in the `.hermes` directory within the workspace.
*   **Non-Interactive Mode:** The agent runs with `HERMES_YOLO_MODE=1`, allowing it to execute tools and commands without waiting for manual confirmation—essential for CI/CD environments.
*   **Bridge Script:** The `scripts/gha_bridge.py` script acts as a translator between GitHub event payloads and the Hermes CLI.

## Security Considerations

*   **YOLO Mode:** In GHA, Hermes runs in "You Only Live Once" mode. It will execute commands automatically. Ensure your `GITHUB_TOKEN` permissions are restricted to the minimum required for the agent's tasks.
*   **Infinite Loops:** The workflow includes a check (`github.actor != 'github-actions[bot]'`) to prevent the agent from responding to its own comments.

## Customization

You can modify `scripts/gha_bridge.py` to change how Hermes parses incoming events or to add logic for posting responses back to the GitHub API.
