---
name: source-discovery
description: Automatically discovers high-quality sources (arXiv, web articles) for a topic and saves them to your Obsidian Research folder for NotebookLM-style processing.
---

# Source Discovery (NotebookLM Pipeline)

This skill automates the "Discovery" phase of the NotebookLM pipeline. It finds high-quality academic papers and authoritative web articles on a topic and saves them directly to your workspace.

## Discovery Workflow
1. **Define Topic**: The user provides a topic (e.g. "Latest trends in GRPO reinforcement learning").
2. **Search Sources**:
   - Use `arxiv` skill to find the latest/most relevant academic papers.
   - Use `web_search` (Tavily/Exa) to find authoritative articles, documentation, or blog posts.
3. **Screen & Select**: Present the top 5-10 findings to the user.
4. **Fetch & Save**:
   - Use `web_fetch` or `web_extract` to get the full text.
   - Save the content as a Markdown file in your `Obsidian/Hermes/Research/` folder.
5. **Auto-Process**: This triggers the `obsidian_ingest.py` daemon to generate a Studio Briefing and Flashcards automatically.

## Usage
Ask Hermes:
- "Find 5 high-quality sources on [Topic] and save them to my research folder."
- "What are the foundational papers for [Topic]? Discovery them for my notebook."

## Why this matters
NotebookLM is only as good as the sources you give it. This skill ensures your "Notebook" is seeded with the highest-signal information before you start your deep dive.
