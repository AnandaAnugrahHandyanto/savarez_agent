"""
Kanban Task Completion Summary Generator

Generates comprehensive AI summaries for completed kanban tasks covering:
- What was done
- How it was done
- Impact
- Key metrics

This module is called by the gateway's kanban notifier after a task completes.
"""
import asyncio
import json
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger(__name__)


async def generate_and_deliver_summary(
    task_id: str,
    board: Optional[str],
    adapter: Any,
    chat_id: str,
    thread_id: Optional[str],
    gateway_runner: Optional[Any] = None,
) -> None:
    """Generate an AI summary for a completed task and deliver it.
    
    This function:
    1. Fetches task details from the kanban DB
    2. Generates an AI summary using the AIAgent
    3. Stores the summary as a comment with author 'hermes-ai-summary'
    4. Sends the summary to the subscribed chat
    
    Runs as a background task; failures are logged but don't block the notifier.
    
    Args:
        task_id: Task ID to generate summary for
        board: Board slug (optional, defaults to current board)
        adapter: Platform adapter for sending the summary
        chat_id: Chat ID to send summary to
        thread_id: Thread ID (optional)
        gateway_runner: GatewayRunner instance for accessing config
    """
    try:
        from hermes_cli import kanban_db as kb
        
        # Fetch task details in a thread
        def _fetch_task_data():
            conn = kb.connect(board=board)
            try:
                task = kb.get_task(conn, task_id)
                if not task:
                    return None, None, None, None
                
                runs = kb.list_runs(conn, task_id)
                latest_run = runs[-1] if runs else None
                
                comments = kb.list_comments(conn, task_id)
                events = kb.list_events(conn, task_id)
                
                return task, latest_run, comments, events
            finally:
                conn.close()
        
        task, run, comments, events = await asyncio.to_thread(_fetch_task_data)
        
        if not task:
            logger.warning(f"kanban summary: task {task_id} not found")
            return
        
        # Check if we should generate a summary
        if not _should_generate_summary(task, run):
            logger.debug(f"kanban summary: skipping trivial task {task_id}")
            return
        
        # Build the summary prompt
        prompt = _build_summary_prompt(task, run, events, comments)
        
        # Generate summary using AIAgent
        summary = await _generate_summary_with_ai(prompt)
        
        if not summary:
            logger.warning(f"kanban summary: AI generation failed for {task_id}")
            return
        
        # Store summary as a comment
        def _store_summary():
            conn = kb.connect(board=board)
            try:
                comment_body = (
                    f"## 📊 AI-Generated Task Summary\n\n"
                    f"{summary}\n\n"
                    f"---\n"
                    f"*Generated automatically on task completion*"
                )
                kb.add_comment(
                    conn,
                    task_id,
                    author="hermes-ai-summary",
                    body=comment_body,
                )
            finally:
                conn.close()
        
        await asyncio.to_thread(_store_summary)
        logger.info(f"kanban summary: generated and stored for {task_id}")
        
        # Format and send the summary
        notification_msg = _format_summary_for_notification(
            summary, task.title, task_id
        )
        
        metadata: Dict[str, Any] = {}
        if thread_id:
            metadata["thread_id"] = thread_id
        
        await adapter.send(chat_id, notification_msg, metadata=metadata)
        logger.info(f"kanban summary: delivered to {chat_id} for {task_id}")
        
    except Exception as exc:
        logger.exception(f"kanban summary: failed for {task_id}: {exc}")


def _should_generate_summary(task: Any, run: Optional[Any] = None) -> bool:
    """Determine if a task completion should trigger summary generation.
    
    Args:
        task: Task object
        run: Latest run object
        
    Returns:
        True if summary should be generated
    """
    # Skip for trivial tasks (no body, very short title)
    if not task.body and len(task.title) < 20:
        return False
    
    # Skip if run has no meaningful content
    if run and not run.summary and not run.metadata:
        return False
    
    # Generate for all other completed tasks
    return True


def _build_summary_prompt(
    task: Any,
    run: Optional[Any] = None,
    events: Optional[list] = None,
    comments: Optional[list] = None,
) -> str:
    """Build the AI prompt for summary generation.
    
    Args:
        task: Task object with title, body, assignee, etc.
        run: Latest run object with summary, metadata, outcome
        events: List of task events
        comments: List of task comments
        
    Returns:
        Formatted prompt string
    """
    context_parts = []
    
    # Task basics
    context_parts.append(f"**Task Title:** {task.title}")
    if task.body:
        body_preview = task.body[:800] if len(task.body) > 800 else task.body
        context_parts.append(f"**Task Description:**\n{body_preview}")
    context_parts.append(f"**Assignee:** {task.assignee or 'unassigned'}")
    
    # Run information
    if run:
        if run.summary:
            context_parts.append(f"**Worker Summary:**\n{run.summary}")
        if run.metadata:
            try:
                # Extract key metrics from metadata
                metadata = run.metadata
                metrics = []
                if "changed_files" in metadata:
                    metrics.append(f"- Files changed: {len(metadata['changed_files'])}")
                if "tests_run" in metadata:
                    metrics.append(f"- Tests run: {metadata['tests_run']}")
                if "tests_passed" in metadata:
                    metrics.append(f"- Tests passed: {metadata['tests_passed']}")
                if metrics:
                    context_parts.append(f"**Metrics:**\n" + "\n".join(metrics))
                
                # Include full metadata for context
                metadata_str = json.dumps(metadata, indent=2)
                context_parts.append(f"**Full Metadata:**\n```json\n{metadata_str}\n```")
            except Exception:
                pass
    
    # Recent comments (last 5)
    if comments:
        recent_comments = comments[-5:]
        if recent_comments:
            comment_lines = []
            for c in recent_comments:
                comment_preview = c.body[:200] if len(c.body) > 200 else c.body
                comment_lines.append(f"- **{c.author}:** {comment_preview}")
            context_parts.append(f"**Recent Comments:**\n" + "\n".join(comment_lines))
    
    context = "\n\n".join(context_parts)
    
    # Generate summary prompt
    prompt = f"""You are analyzing a completed kanban task. Generate a concise, informative summary that covers:

1. **What was done**: Core deliverables and outcomes (2-3 sentences)
2. **How it was done**: Key approach, methods, or tools used (1-2 sentences)
3. **Impact**: What changed, what value was delivered, or what problem was solved (1-2 sentences)
4. **Key metrics**: Quantifiable results if available (bullet points)

Be specific and factual. Use the worker's summary and metadata as the primary source of truth. If the task failed or was blocked, explain why clearly.

Task Context:
{context}

Generate a clear, professional summary in 3-4 short paragraphs. Use markdown formatting. Keep it under 600 words."""
    
    return prompt


async def _generate_summary_with_ai(prompt: str) -> Optional[str]:
    """Generate summary using AIAgent.
    
    Args:
        prompt: Summary generation prompt
        
    Returns:
        Generated summary text, or None if generation failed
    """
    try:
        from run_agent import AIAgent
        from hermes_cli.config import load_config
        
        # Load config for model settings
        config = load_config()
        
        # Use a fast model for quick summaries
        # Prefer sonnet-4 for quality, fall back to configured model
        model = config.get("model", "claude-sonnet-4")
        provider = config.get("provider", "anthropic")
        
        # Create a lightweight AIAgent for summary generation
        agent = AIAgent(
            model=model,
            provider=provider,
            max_iterations=1,  # Single-shot generation
            quiet_mode=True,
            save_trajectories=False,
            skip_memory=True,  # Don't load memory for summary generation
            enabled_toolsets=[],  # No tools needed
            platform="kanban-summary",  # Identify the context
        )
        
        # Generate summary in a thread
        def _generate():
            return agent.chat(prompt)
        
        summary = await asyncio.to_thread(_generate)
        return summary
        
    except Exception as exc:
        logger.exception(f"kanban summary: AI generation error: {exc}")
        return None


def _format_summary_for_notification(
    summary: str,
    task_title: str,
    task_id: str,
    max_length: int = 1000,
) -> str:
    """Format a summary for notification delivery.
    
    Args:
        summary: Full AI-generated summary
        task_title: Task title for context
        task_id: Task ID
        max_length: Maximum message length
        
    Returns:
        Formatted notification message
    """
    header = f"📊 **Task Summary: {task_title}**\n`{task_id}`\n\n"
    footer = "\n\n💡 *Full summary stored in task comments*"
    
    available_length = max_length - len(header) - len(footer)
    
    if len(summary) <= available_length:
        body = summary
    else:
        # Truncate at paragraph boundary if possible
        paragraphs = summary.split('\n\n')
        body = ""
        for para in paragraphs:
            if len(body) + len(para) + 2 <= available_length:
                body += para + "\n\n"
            else:
                break
        
        if not body:
            # No complete paragraph fits, truncate at word boundary
            body = summary[:available_length].rsplit(' ', 1)[0] + "..."
        else:
            body = body.strip()
    
    return header + body + footer
