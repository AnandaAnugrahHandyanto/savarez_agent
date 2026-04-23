"""GitLab MR Review Plugin — native tools for reviewing GitLab Merge Requests.

Registers 7 tools across 3 categories:

MR Tools (5):
  gitlab_mr_view, gitlab_mr_review_start, gitlab_mr_comment,
  gitlab_mr_review_submit, gitlab_mr_list

Pipeline Tools (1):
  gitlab_mr_pipelines

Context Tools (1):
  gitlab_mr_discussions

Review flow:
  1. gitlab_mr_review_start — open a buffered review session
  2. gitlab_mr_comment — buffer comments (general or inline)
  3. gitlab_mr_review_submit — post all comments at once (summary first)

Hooks:
  on_session_end — warns if review buffer has unflushed comments

Configuration via environment variables:
  GITLAB_TOKEN   — Personal access token (required). Needs api + read_api scope.
  GITLAB_URL     — Base URL for self-hosted GitLab (default: https://gitlab.com).
"""


def register(ctx) -> None:
    """Register all GitLab MR review tools with the plugin system."""
    from plugins.gitlab_review.tools_mr import register_mr_tools, _flush_warning
    from plugins.gitlab_review.tools_pipeline import register_pipeline_tools
    from plugins.gitlab_review.tools_context import register_context_tools

    register_mr_tools(ctx)
    register_pipeline_tools(ctx)
    register_context_tools(ctx)

    # Register on_session_end hook to warn about unflushed review buffers
    def _on_session_end(**kwargs):
        warning = _flush_warning()
        if warning:
            import logging
            logging.getLogger(__name__).warning(warning)

    ctx.register_hook("on_session_end", _on_session_end)
