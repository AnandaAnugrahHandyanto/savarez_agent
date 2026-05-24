"""Tests for deterministic accessibility snapshot to Markdown rendering."""

from __future__ import annotations


SNAPSHOT = """
- document:
  - heading "Example Domain" [level=1] [ref=e1]
  - paragraph: This domain is for use in documentation examples without needing permission.
  - link "Learn more" [ref=e2]:
    - /url: https://iana.org/domains/example
  - button "Accept cookies" [ref=e3]
  - textbox "Search" [ref=e4]
"""

DOCS_SNAPSHOT = """
- generic:
  - navigation "Main":
    - link "Docs" [ref=e1]:
      - /url: /docs/user-stories
  - main:
    - article:
      - heading "Hermes Agent" [level=1]
      - paragraph:
        - text: The self-improving AI agent built by
        - link "Nous Research" [ref=e2]:
          - /url: https://nousresearch.com
        - text: . The only agent with a built-in learning loop.
      - generic:
        - link "Get Started →" [ref=e3]:
          - /url: /docs/getting-started/installation
      - heading "InstallDirect link to Install" [level=2]:
        - text: Install
        - link "Direct link to Install" [ref=e4]:
          - /url: "#install"
          - text: "#"
      - paragraph:
        - strong: Linux / macOS / WSL2
      - generic:
        - code:
          - generic: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
          - button "Copy code to clipboard" [ref=e5]
      - paragraph:
        - strong: Windows (native, PowerShell)
        - text: —
        - emphasis:
          - text: early beta,
          - link "details →" [ref=e6]:
            - /url: /docs/user-guide/windows-native
      - paragraph:
        - text: See the full
        - strong:
          - link "Installation Guide" [ref=e7]:
            - /url: /docs/getting-started/installation
        - text: for details.
      - heading "Quick LinksDirect link to Quick Links" [level=2]:
        - text: Quick Links
        - link "Direct link to Quick Links" [ref=e8]:
          - /url: "#quick-links"
          - text: "#"
      - table:
        - rowgroup:
          - row "🚀 Installation Install in 60 seconds on Linux, macOS, WSL2, or native Windows (early beta)":
            - cell "🚀 Installation":
              - text: 🚀
              - strong:
                - link "Installation" [ref=e9]:
                  - /url: /docs/getting-started/installation
            - cell "Install in 60 seconds on Linux, macOS, WSL2, or native Windows (early beta)"
"""

GITHUB_REPO_SNAPSHOT = """
- main:
  - generic:
    - link "NousResearch" [ref=e1]:
      - /url: /NousResearch
    - strong:
      - link "hermes-agent" [ref=e2]:
        - /url: /NousResearch/hermes-agent
    - list:
      - listitem:
        - link "You must be signed in to change notification settings" [ref=e3]:
          - /url: /login?return_to=%2FNousResearch%2Fhermes-agent
          - text: Notifications
      - listitem:
        - link "Fork 21.8k" [ref=e4]:
          - /url: /login?return_to=%2FNousResearch%2Fhermes-agent
  - generic:
    - heading "NousResearch/hermes-agent" [level=1]
    - table "Folders and files":
      - rowgroup:
        - row "Name Last commit message Last commit date":
          - columnheader "Name"
          - columnheader "Last commit message"
          - columnheader "Last commit date"
        - row ".github, (Directory) ci: run docker build May 9, 2026":
          - cell ".github, (Directory)":
            - link ".github, (Directory)" [ref=e5]:
              - /url: /NousResearch/hermes-agent/tree/main/.github
              - text: .github
          - cell "ci: run docker build"
          - cell "May 9, 2026"
"""


def test_renders_headings_paragraphs_and_links_without_refs_or_controls():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(SNAPSHOT)

    assert "# Example Domain" in markdown
    assert "This domain is for use in documentation examples" in markdown
    assert "[Learn more](https://iana.org/domains/example)" in markdown
    assert "ref=e" not in markdown
    assert "[e2]" not in markdown
    assert "Accept cookies" not in markdown
    assert "Search" not in markdown


def test_can_emit_refs_and_controls_for_future_reuse():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        SNAPSHOT,
        emit_refs=True,
        emit_controls=True,
    )

    assert "# Example Domain [e1]" in markdown
    assert "[Learn more](https://iana.org/domains/example) [e2]" in markdown
    assert '<button "Accept cookies" [e3]>' in markdown
    assert '<textbox "Search" [e4]>' in markdown


def test_strips_legacy_at_refs_when_refs_are_disabled():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown('- link "Docs" @e12:\n  - /url: https://example.com/docs')

    assert markdown == "[Docs](https://example.com/docs)"
    assert "@e12" not in markdown


def test_non_ascii_snapshot_text_is_not_mojibaked():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown('- heading "Être Free" [level=1]')

    assert markdown == "# Être Free"


def test_unknown_or_malformed_roles_return_safe_text_without_crashing():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- application "Metrics" [ref=e8]\n'
        '  - meter "CPU 42%"\n'
        '  - garbled line without a useful role\n'
    )

    assert "Metrics" in markdown
    assert "CPU 42%" in markdown
    assert "ref=e8" not in markdown


def test_renders_main_content_without_global_navigation_noise():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(DOCS_SNAPSHOT)

    assert markdown.startswith("# Hermes Agent")
    assert "[Docs](/docs/user-stories)" not in markdown
    assert "Main" not in markdown


def test_merges_inline_paragraph_fragments_and_punctuation():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(DOCS_SNAPSHOT)

    assert "The self-improving AI agent built by [Nous Research](https://nousresearch.com). The only agent" in markdown
    assert "built by\n[Nous Research]" not in markdown
    assert "https://nousresearch.com) ." not in markdown
    assert "**Windows (native, PowerShell)** — *early beta, [details →](/docs/user-guide/windows-native)*" in markdown
    assert "See the full **[Installation Guide](/docs/getting-started/installation)** for details." in markdown


def test_strips_docusaurus_direct_anchor_noise_from_headings():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(DOCS_SNAPSHOT)

    assert "## Install" in markdown
    assert "## Quick Links" in markdown
    assert "Direct link to" not in markdown
    assert "\n#\n" not in markdown
    assert "InstallDirect" not in markdown


def test_renders_code_blocks_and_table_rows_compactly():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(DOCS_SNAPSHOT)

    assert "```\ncurl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash\n```" in markdown
    assert "- 🚀 **[Installation](/docs/getting-started/installation)**: Install in 60 seconds on Linux" in markdown
    assert "🚀 Installation Install in 60 seconds" not in markdown


def test_drops_github_repo_action_preamble_before_primary_heading():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(GITHUB_REPO_SNAPSHOT)

    assert markdown.startswith("# NousResearch/hermes-agent")
    assert "Notifications" not in markdown
    assert "Fork 21.8k" not in markdown
    assert "| [.github](/NousResearch/hermes-agent/tree/main/.github) | ci: run docker build | May 9, 2026 |" in markdown


def test_renders_plain_lists_without_blank_lines_between_items():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- main:\n'
        '  - list:\n'
        '    - listitem: First item\n'
        '    - listitem: Second item\n'
    )

    assert markdown == "- First item\n- Second item"


def test_preserves_repeated_content_and_code_lines():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- main:\n'
        '  - paragraph: echo\n'
        '  - paragraph: echo\n'
        '  - code:\n'
        '    - generic: repeat\n'
        '    - generic: repeat\n'
    )

    assert markdown.count("echo") == 2
    assert "```\nrepeat\nrepeat\n```" in markdown


def test_preserves_meaningful_image_alt_text():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown('- main:\n  - img "Architecture diagram"\n')

    assert markdown == "![Architecture diagram]"


def test_strips_private_use_glyph_only_text():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- main:\n'
        '  - heading "Real content" [level=1]\n'
        '  - paragraph: \ue001\n'
        '  - paragraph: Body text\n'
    )

    assert markdown == "# Real content\n\nBody text"


def test_skips_javascript_links_in_document_output():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- main:\n'
        '  - link "Open menu" [ref=e1]:\n'
        '    - /url: javascript:void(0)\n'
        '  - link "Real link" [ref=e2]:\n'
        '    - /url: https://example.com\n'
    )

    assert "javascript:" not in markdown
    assert "Open menu" not in markdown
    assert markdown == "[Real link](https://example.com)"


def test_keeps_javascript_links_when_refs_are_explicitly_requested():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- main:\n'
        '  - link "Open menu" [ref=e1]:\n'
        '    - /url: javascript:void(0)\n',
        emit_refs=True,
    )

    assert markdown == "[Open menu](javascript:void(0)) [e1]"


def test_skips_footer_toolbar_and_menu_chrome_without_main_landmark():
    from tools.web_accessibility_markdown import render_accessibility_markdown

    markdown = render_accessibility_markdown(
        '- document:\n'
        '  - toolbar:\n'
        '    - button "Refresh" [ref=e1]\n'
        '  - menu:\n'
        '    - menuitem "Account" [ref=e2]\n'
        '  - heading "Article" [level=1]\n'
        '  - paragraph: Body\n'
        '  - contentinfo:\n'
        '    - link "Privacy" [ref=e3]:\n'
        '      - /url: /privacy\n'
    )

    assert markdown == "# Article\n\nBody"
    assert "Refresh" not in markdown
    assert "Account" not in markdown
    assert "Privacy" not in markdown
