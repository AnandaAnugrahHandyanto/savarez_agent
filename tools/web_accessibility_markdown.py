"""Deterministic Markdown renderer for browser accessibility snapshots.

This module converts Playwright accessibility snapshots into clean, readable
Markdown. It is intentionally dependency-free and used by Camofox-backed
web extraction (not browser tools), so the default output strips actionable
refs and controls.

Architecture:
- Phase 0: Parse accessibility tree with robust escape handling
- Phase 1: Multi-pass rendering with normalization and transforms
- Phase 2: Markdown-safe inline formatting
- Phase 3: Structural improvements (tables, lists, etc.)
- Phase 4: Polish (consent dialogs, chrome compaction)
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


# ============================================================================
# Phase 0: Parser helpers
# ============================================================================


def _decode_accessible_string_escapes(value: str) -> str:
    """Decode escape sequences in accessibility strings.

    Handles \\n, \\t, \\\\, \\", \\' explicitly. Unknown escapes kept literally.
    This is safer than ast.literal_eval which can fail on non-Python escapes.
    """
    if not value:
        return ""

    result = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value):
            next_char = value[i + 1]
            if next_char == "n":
                result.append("\n")
                i += 2
            elif next_char == "t":
                result.append("\t")
                i += 2
            elif next_char == "\\":
                result.append("\\")
                i += 2
            elif next_char == '"':
                result.append('"')
                i += 2
            elif next_char == "'":
                result.append("'")
                i += 2
            else:
                # Unknown escape, keep literally
                result.append(value[i])
                i += 1
        else:
            result.append(value[i])
            i += 1

    return "".join(result)


def _unquote_aria_snapshot_key(key: str) -> str:
    """Unwrap YAML-quoted ariaSnapshot keys without treating inner colons as separators.

    Handles:
    - "text: with colon" -> text: with colon
    - 'O\\'Brien' -> O'Brien
    - heading -> heading (bare)
    """
    key = (key or "").strip()
    if len(key) >= 2 and key[0] == '"' and key[-1] == '"':
        return _decode_accessible_string_escapes(key[1:-1])
    if len(key) >= 2 and key[0] == "'" and key[-1] == "'":
        return key[1:-1].replace("''", "'")
    return key


def _split_unquoted_colon(text: str) -> tuple[str, str]:
    """Split a Playwright ariaSnapshot map-ish line on the first structural colon.

    Respects:
    - Quoted strings (single/double)
    - Escaped quotes
    - Bracket depth [...]
    """
    escaped = False
    quote: Optional[str] = None
    bracket_depth = 0

    for idx, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in {'"', "'"}:
            quote = ch
            continue
        if ch == "[":
            bracket_depth += 1
            continue
        if ch == "]" and bracket_depth:
            bracket_depth -= 1
            continue
        if ch == ":" and bracket_depth == 0:
            return text[:idx].strip(), text[idx + 1:].strip()

    return text.strip(), ""


def _parse_quoted_name(rest: str) -> tuple[str, str]:
    """Parse a quoted name from the rest of a line.

    Returns: (name, remaining_text)
    """
    if not rest.startswith('"'):
        return "", rest

    # Find matching close quote, handling escapes
    i = 1
    name_chars = []
    while i < len(rest):
        ch = rest[i]
        if ch == "\\" and i + 1 < len(rest):
            next_ch = rest[i + 1]
            if next_ch == "n":
                name_chars.append("\n")
                i += 2
            elif next_ch == "t":
                name_chars.append("\t")
                i += 2
            elif next_ch in ('"', "'", "\\"):
                name_chars.append(next_ch)
                i += 2
            else:
                name_chars.append(ch)
                i += 1
        elif ch == '"':
            # Found close quote
            name = "".join(name_chars)
            remaining = rest[i + 1:].strip()
            return name, remaining
        else:
            name_chars.append(ch)
            i += 1

    # No close quote found, return what we have
    return "".join(name_chars), ""


def _parse_regex_name(rest: str) -> tuple[str, str, str]:
    """Parse a regex name like /^pattern/ from the rest of a line.

    Returns: (role, name, remaining_text)
    Note: This is a simplified version. The actual role is extracted elsewhere.
    """
    if not rest.startswith("/"):
        return "", "", rest

    # Find matching close slash, handling escapes
    i = 1
    while i < len(rest):
        if rest[i] == "\\" and i + 1 < len(rest):
            i += 2  # Skip escaped char
        elif rest[i] == "/":
            # Found close slash
            name = rest[:i + 1]
            remaining = rest[i + 1:].strip()
            return "", name, remaining
        else:
            i += 1

    # No close slash found
    return "", rest, ""


_KNOWN_ARIA_ROLES = {
    "fragment", "page", "document", "application", "main", "article", "region", "section", "group",
    "generic", "none", "presentation", "banner", "navigation", "contentinfo", "complementary",
    "toolbar", "menu", "menubar", "tablist", "tabpanel", "dialog", "alertdialog", "search", "form",
    "feed", "log", "marquee", "math", "timer", "tooltip", "heading", "paragraph", "text", "caption",
    "status", "alert", "note", "time", "blockquote", "figure", "list", "listitem", "link", "img",
    "image", "iframe", "table", "grid", "tree", "treegrid", "treeitem", "row", "rowgroup", "cell",
    "gridcell", "columnheader", "rowheader", "code", "pre", "strong", "emphasis", "em", "italic",
    "button", "textbox", "searchbox", "combobox", "checkbox", "radio", "radiogroup", "switch",
    "menuitem", "menuitemcheckbox", "menuitemradio", "tab", "option", "listbox", "slider",
    "spinbutton", "meter", "progressbar", "scrollbar", "separator", "term", "definition",
    "deletion", "insertion", "subscript", "superscript",
}


def _is_known_aria_role(role: str) -> bool:
    """Check if a role is a known ARIA role."""
    return role in _KNOWN_ARIA_ROLES


# Regex patterns for parsing
_ROLE_RE = re.compile(
    r"^\s*(?:-\s*)?['\"]?(?P<role>[A-Za-z][\w-]*)['\"]?"
    r"(?P<rest>.*)$"
)
_QUOTED_NAME_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_REF_RE = re.compile(r"\[(?:ref=)?(?P<ref>e\d+)\]|(?<!\S)@(?P<atref>e\d+)(?=\s|:|$)")
_LEVEL_RE = re.compile(r"\[level=(?P<level>\d+)\]")
_URL_RE = re.compile(r"^\s*(?:-\s*)?/url:\s*(?P<url>.+?)\s*$")
_COLON_TEXT_RE = re.compile(r"^\s*(?:\[[^\]]+\]\s*)*:\s*(?P<text>.+?)\s*$")
_VALUE_RE = re.compile(r":\s*value:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
_STATE_RE = re.compile(r"\[(?P<state>[^\]]+)\]")

_CONTROL_ROLES = {
    "button",
    "textbox",
    "searchbox",
    "combobox",
    "checkbox",
    "radio",
    "switch",
    "slider",
    "spinbutton",
    "menuitem",
    "menuitemcheckbox",
    "menuitemradio",
    "option",
    "tab",
}
_CONTAINER_ROLES = {
    "root",
    "document",
    "main",
    "article",
    "section",
    "group",
    "region",
    "generic",
    "list",
    "rowgroup",
    "iframe",  # Phase 3.14
}
_SKIP_SUBTREE_ROLES = {
    "navigation",
    "banner",
    "contentinfo",
    "complementary",
    "search",
    "toolbar",
    "menu",
    "menubar",
}
_INLINE_ROLES = {
    "text",
    "strong",
    "emphasis",
    "em",
    "italic",
    "deletion",
    "term",
    "definition",
    "caption",
    "meter",
    "progressbar",  # Phase 3.13
    "generic",
    "cell",
    "gridcell",  # Phase 3.15
    "columnheader",
    "rowheader",  # Phase 3.15
}
_IMAGE_ROLES = {"img", "image"}
_TRACKING_QUERY_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}  # Phase 3.5


@dataclass
class _Item:
    role: str
    text: str
    ref: str = ""
    level: int = 0
    url: str = ""
    indent: int = 0
    children: list["_Item"] = field(default_factory=list)
    value: str = ""  # Phase 2.7: Control value
    states: list[str] = field(default_factory=list)  # Phase 2.7: Control states
    props: dict = field(default_factory=dict)  # Phase 2.3: Props like class
    meta: dict = field(default_factory=dict)  # Phase 3.7: Metadata
    parent: Optional["_Item"] = None  # Phase 4.1: Parent reference


def render_accessibility_markdown(
    snapshot_text: str,
    *,
    url: str = "",
    title: str = "",
    emit_refs: bool = False,
    emit_controls: bool = False,
) -> str:
    """Render accessibility snapshot text to stable Markdown.

    The caller owns the source contract. Camofox extraction passes accessibility
    snapshots here; other web backends do not route through this renderer.
    """
    if not isinstance(snapshot_text, str):
        return ""

    text = snapshot_text.strip()
    if not text:
        return ""

    # Phase 0: Parse tree
    root = _parse_tree(text)

    # Phase 3.7: Annotate tree
    _annotate_tree(root)

    # Phase 3.6: Reorder children for readability
    content_nodes = _select_content_nodes(root)

    # Phase 1: Render with multi-pass pipeline
    blocks = _render_nodes(content_nodes, emit_refs=emit_refs, emit_controls=emit_controls)

    # Phase 1.1-1.2: Normalize and transform
    output = _join_blocks(blocks)

    # Phase 1.3: Handle title
    if title:
        output = _handle_title(output, title)

    return output


# ============================================================================
# Parsing
# ============================================================================


def _parse_tree(text: str) -> _Item:
    root = _Item(role="root", text="", indent=-1)
    stack: list[_Item] = [root]

    for line in text.splitlines():
        if not line.strip():
            continue
        node = _parse_line(line)
        if node is None:
            continue
        while stack and node.indent <= stack[-1].indent:
            stack.pop()
        node.parent = stack[-1]  # Phase 4.1: Set parent reference
        stack[-1].children.append(node)
        stack.append(node)

    return root


def _has_descendant_role(node: _Item, role: str) -> bool:
    """Check if a node or any of its descendants has a specific role."""
    if node.role == role:
        return True
    for child in node.children:
        if _has_descendant_role(child, role):
            return True
    return False


def _parse_line(line: str) -> Optional[_Item]:
    indent = len(line) - len(line.lstrip(" "))
    url_match = _URL_RE.match(line)
    if url_match:
        return _Item(role="/url", text="", url=_clean_url(url_match.group("url")), indent=indent)

    parsed = _parse_role_line(line)
    if parsed:
        parsed.indent = indent
    return parsed


def _parse_role_line(line: str) -> Optional[_Item]:
    match = _ROLE_RE.match(line)
    if not match:
        return None

    role = match.group("role").lower()
    rest = match.group("rest") or ""
    if role == "url":
        return None

    # Phase 0.3: Use structural colon splitting
    key_part, value_part = _split_unquoted_colon(line.strip().lstrip("- ").strip())

    # Phase 0.2: Unquote the key
    unquoted_key = _unquote_aria_snapshot_key(key_part)

    # Try to parse quoted name from rest
    quoted = _QUOTED_NAME_RE.search(rest)
    if quoted:
        raw_name = quoted.group(1)
        if "\\" in raw_name:
            # Phase 0.1: Use robust escape decoder
            name = _decode_accessible_string_escapes(raw_name)
        else:
            name = raw_name
    else:
        # Try colon text
        colon = _COLON_TEXT_RE.search(rest)
        if colon:
            name = colon.group("text")
        else:
            # Check for value: pattern
            value_match = _VALUE_RE.search(rest)
            if value_match:
                name = ""
            elif role not in _CONTAINER_ROLES:
                # Last-resort: remove metadata/ref fragments and keep useful prose.
                name = re.sub(r"\[[^\]]+\]", "", rest).strip(" :-'")
            else:
                name = ""

    # Phase 2.7: Parse value and states
    value = ""
    states = []
    value_match = _VALUE_RE.search(rest)
    if value_match:
        raw_value = value_match.group("value").strip()
        # Unquote if needed
        if (raw_value.startswith('"') and raw_value.endswith('"')) or \
           (raw_value.startswith("'") and raw_value.endswith("'")):
            value = _decode_accessible_string_escapes(raw_value[1:-1])
        else:
            value = raw_value

    # Parse states like [checked], [disabled], [expanded]
    for state_match in _STATE_RE.finditer(rest):
        state_text = state_match.group("state").strip()
        # Skip ref, level, nth, cursor
        if state_text.startswith("ref=") or state_text.startswith("level=") or \
           state_text.startswith("nth=") or state_text.startswith("cursor="):
            continue
        if state_text and state_text not in ("checked=false", "checked: false"):
            states.append(state_text)

    # Phase 2.3: Parse props like [class="language-python"]
    props = {}
    prop_match = re.search(r'\[class="([^"]+)"\]', rest)
    if prop_match:
        props["class"] = prop_match.group(1)

    if not name and role not in _CONTAINER_ROLES:
        # Last-resort: remove metadata/ref fragments and keep useful prose.
        name = re.sub(r"\[[^\]]+\]", "", rest).strip(" :-'")

    ref_match = _REF_RE.search(rest)
    ref = ""
    if ref_match:
        ref = ref_match.group("ref") or ref_match.group("atref") or ""

    level_match = _LEVEL_RE.search(rest)
    level = 0
    if level_match:
        try:
            level = max(1, min(6, int(level_match.group("level"))))
        except ValueError:
            level = 0

    # Phase 0.5: Validate role (skip unknown roles without browser markers)
    if not _is_known_aria_role(role) and not ref and level == 0 and not states:
        # Unknown role with no markers, skip it
        return None

    return _Item(
        role=role,
        text=_strip_refs(name).strip(),
        ref=ref,
        level=level,
        value=value,
        states=states,
        props=props,
    )


# ============================================================================
# Phase 3.7: Tree annotation
# ============================================================================


def _annotate_tree(node: _Item, depth: int = 0) -> None:
    """Annotate tree with metadata for rendering."""
    if node.role == "listitem":
        node.meta["list_depth"] = depth

    # Check for explicit table headers
    if node.role == "table":
        has_header = any(
            cell.role in {"columnheader", "rowheader"}
            for row in _find_nodes(node, "row")
            for cell in row.children
            if cell.role in {"cell", "columnheader", "rowheader", "gridcell"}
        )
        node.meta["has_explicit_header"] = has_header

    # Detect code language
    if node.role in {"code", "pre"}:
        lang = _code_language_label(node)
        if lang:
            node.meta["language"] = lang

    for child in node.children:
        _annotate_tree(child, depth + 1 if node.role == "listitem" else depth)


# ============================================================================
# Phase 3.6: Readable ordering
# ============================================================================


def _select_content_nodes(root: _Item) -> list[_Item]:
    mains = _find_nodes(root, "main")
    if mains:
        return _ordered_readable_children(mains)
    articles = _find_nodes(root, "article")
    if articles:
        return _ordered_readable_children(articles)
    return _ordered_readable_children(root.children)


def _ordered_readable_children(children: list[_Item]) -> list[_Item]:
    """Reorder children: main/article first, then sections, then chrome."""
    _CHROME_ROLES = {"banner", "navigation", "search", "form", "complementary", "toolbar", "menu", "menubar"}
    _PRIMARY_ROLES = {"main", "article"}
    _SECONDARY_ROLES = {"section", "region", "group"}

    def priority(node: _Item) -> int:
        if node.role in _PRIMARY_ROLES:
            return 0
        if node.role in _SECONDARY_ROLES:
            return 1
        if node.role in _CHROME_ROLES or node.role == "contentinfo":
            return 2
        return 1

    # Stable sort by priority
    return sorted(children, key=priority)


def _find_nodes(node: _Item, role: str) -> list[_Item]:
    found: list[_Item] = []
    if node.role == role:
        found.append(node)
    for child in node.children:
        found.extend(_find_nodes(child, role))
    return found


# ============================================================================
# Phase 4.1: Chrome compaction
# ============================================================================


def _compact_item_nodes(node: _Item) -> list[_Item]:
    """Recursively collect links and controls from a chrome node."""
    if node.role == "link" or node.role in _CONTROL_ROLES:
        return [node]
    items = []
    for child in node.children:
        items.extend(_compact_item_nodes(child))
    return items


def _chrome_title(node: _Item) -> str:
    """Generate a title for compacted chrome sections."""
    if node.role == "banner":
        return "Header"
    if node.role == "contentinfo":
        return "Footer"
    if node.role in {"menu", "menubar", "toolbar"}:
        return "Navigation"
    if node.role == "search":
        return "Search"
    if node.role == "form":
        return "Form"
    # navigation or other
    return node.role.replace("-", " ").title()


def _compact_chrome_node(node: _Item, *, emit_refs: bool, emit_controls: bool) -> Optional[list[str]]:
    """Compact chrome sections (nav, banner, etc.) into a single-line summary.
    
    Returns rendered lines or None if not compactable.
    """
    _CHROME_ROLES = {"banner", "navigation", "toolbar", "menu", "menubar", "contentinfo", "search", "form"}
    
    if node.role not in _CHROME_ROLES:
        return None
    
    # Don't compact if emit_controls is True (user wants full detail)
    if emit_controls:
        return None
    
    # Check if this chrome node is a direct child of a document with no main content
    # In that case, skip chrome entirely (return empty list)
    if node.parent and node.parent.role == "document":
        has_main = _has_descendant_role(node.parent, "main")
        if not has_main:
            return []  # Skip chrome entirely
    
    # Collect items
    items = _compact_item_nodes(node)
    if not items:
        return None
    
    # Don't compact if there's substantive block content
    if _has_substantive_block_content(node):
        return None
    
    # Render items
    rendered_items = []
    seen = set()
    for item in items:
        text = _inline_fragment(item, emit_refs=emit_refs)
        if not text:
            continue
        key = text.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        rendered_items.append(text)
    
    if not rendered_items:
        return None
    
    # Cap at 6 items if more than 8
    if not emit_refs and len(rendered_items) > 8:
        rendered_items = rendered_items[:6] + [f"… {len(rendered_items) - 6} more"]
    
    title = _chrome_title(node)
    return [f"## {title}", "- " + ", ".join(rendered_items)]


def _has_substantive_block_content(node: _Item) -> bool:
    """Check if a node contains substantive block content (not just chrome)."""
    if node.role in {"main", "article", "paragraph", "blockquote", "table", "grid", "treegrid", "code", "pre"}:
        return True
    if node.role == "heading" and _clean_ui_text(node.text):
        return True
    if node.role == "listitem":
        text = _clean_ui_text(node.text)
        if len(text) > 80:
            return True
        for child in node.children:
            if child.role in {"paragraph", "code", "pre", "table", "grid", "treegrid"}:
                return True
    for child in node.children:
        if _has_substantive_block_content(child):
            return True
    return False


# ============================================================================
# Phase 4.2: Consent dialog detection
# ============================================================================


def _is_consent_node(node: _Item) -> bool:
    """Check if a node is a cookie/privacy consent dialog."""
    if node.role not in {"dialog", "alertdialog"}:
        return False
    
    text = (node.text or "").lower()
    consent_keywords = ["cookie", "consent", "privacy", "legitimate interest"]
    if not any(keyword in text for keyword in consent_keywords):
        return False
    
    # Check for accept/reject controls
    controls = []
    for child in _compact_item_nodes(node):
        if child.role in _CONTROL_ROLES:
            controls.append(_clean_ui_text(child.text).lower())
    
    action_keywords = ["accept", "reject", "manage", "choices", "options"]
    return any(any(keyword in label for keyword in action_keywords) for label in controls)


def _render_consent_node(node: _Item, *, emit_refs: bool, emit_controls: bool) -> Optional[list[str]]:
    """Render consent dialogs compactly.
    
    Returns rendered lines or None if not a consent dialog.
    """
    if not _is_consent_node(node):
        return None
    
    # Collect text parts
    text_parts = []
    controls = []
    
    def walk(current: _Item) -> None:
        if current.role in _CONTROL_ROLES:
            rendered = _render_control(current, emit_refs=emit_refs)
            if rendered:
                controls.append(rendered)
            return
        if current.role in {"heading", "paragraph", "text", "caption", "status", "alert", "note"}:
            text = _inline_text(current.children, emit_refs=emit_refs) if current.children else _clean_ui_text(current.text)
            if text:
                text_parts.append(text)
            return
        for child in current.children:
            walk(child)
    
    walk(node)
    
    lines = ["## Consent"]
    
    # Join unique text parts with em-dash
    unique_parts = []
    seen = set()
    for part in text_parts:
        normalized = part.strip()
        if normalized and normalized.lower() not in seen:
            seen.add(normalized.lower())
            unique_parts.append(normalized)
    
    if unique_parts:
        lines.append(" — ".join(unique_parts))
    
    # Add controls if emit_controls is True
    if emit_controls:
        seen_controls = set()
        for control in controls:
            if control not in seen_controls:
                seen_controls.add(control)
                lines.append(control)
    
    return lines


# ============================================================================
# Phase 3.8: Term-definition pairs
# ============================================================================


def _render_term_definition_pair(term: _Item, definition: _Item, *, emit_refs: bool) -> Optional[str]:
    """Render a term-definition pair as **term:** definition.
    
    Returns rendered text or None if invalid.
    """
    term_text = _inline_text(term.children, emit_refs=emit_refs) if term.children else _clean_ui_text(term.text)
    definition_text = _inline_text(definition.children, emit_refs=emit_refs) if definition.children else _clean_ui_text(definition.text)
    
    if not term_text or not definition_text:
        return None
    
    # Remove trailing colon from term if present
    term_text = term_text.rstrip(":")
    
    return f"**{term_text}:** {definition_text}"


# ============================================================================
# Rendering
# ============================================================================


def _render_nodes(nodes: list[_Item], *, emit_refs: bool, emit_controls: bool) -> list[str]:
    blocks: list[str] = []
    pending_inline: list[str] = []
    
    def flush_inline():
        if pending_inline:
            # Join inline fragments with proper spacing
            text = _format_inline_spacing(pending_inline)
            if text:
                blocks.append(text)
            pending_inline.clear()
    
    i = 0
    while i < len(nodes):
        node = nodes[i]
        
        # Phase 3.8: Detect term-definition pairs
        if node.role == "term" and i + 1 < len(nodes) and nodes[i + 1].role == "definition":
            flush_inline()  # Flush any pending inline content first
            term_node = node
            definition_node = nodes[i + 1]
            pair_result = _render_term_definition_pair(term_node, definition_node, emit_refs=emit_refs)
            if pair_result:
                blocks.append(pair_result)
                i += 2  # Skip both term and definition
                continue
        
        # Phase 3.9: Batch consecutive inline fragments
        # Only batch truly inline content (text, formatting), not links or code blocks
        _INLINE_FRAGMENT_ROLES = {"text", "strong", "emphasis", "em", "italic", 
                                   "deletion", "insertion", "subscript", "superscript"}
        if emit_controls:
            _INLINE_FRAGMENT_ROLES.update(_CONTROL_ROLES)
        
        if node.role in _INLINE_FRAGMENT_ROLES:
            # Render inline fragment and add to pending batch
            fragment = _inline_fragment(node, emit_refs=emit_refs)
            if fragment:
                pending_inline.append(fragment)
                i += 1
                continue
            # If fragment is empty (e.g., skipped control), fall through to normal rendering
        
        # Not an inline fragment - flush pending and render normally
        flush_inline()
        blocks.extend(_render_node(node, emit_refs=emit_refs, emit_controls=emit_controls))
        i += 1
    
    # Flush any remaining inline content
    flush_inline()
    return blocks


def _render_node(node: _Item, *, emit_refs: bool, emit_controls: bool) -> list[str]:
    role = node.role

    # Phase 4.2: Consent dialog detection (before generic dialog handling)
    if role in {"dialog", "alertdialog"}:
        consent_result = _render_consent_node(node, emit_refs=emit_refs, emit_controls=emit_controls)
        if consent_result is not None:
            return consent_result

    # Phase 4.1: Chrome compaction (before generic chrome handling)
    _CHROME_ROLES = {"banner", "navigation", "toolbar", "menu", "menubar", "contentinfo", "search", "form"}
    if role in _CHROME_ROLES:
        chrome_result = _compact_chrome_node(node, emit_refs=emit_refs, emit_controls=emit_controls)
        if chrome_result is not None:
            return chrome_result

    # Phase 3.13: Handle meter/progressbar
    if role in {"meter", "progressbar"}:
        label = _clean_ui_text(node.text)
        value_text = _clean_ui_text(node.value) if node.value else ""
        if label and value_text:
            text = f"{label}: {value_text}"
        elif label:
            text = label
        elif value_text:
            text = value_text
        else:
            return []
        if emit_refs and node.ref:
            text = f"{text} [{node.ref}]"
        return [text] if text else []

    if role == "list":
        rendered_items = []
        for child in node.children:
            if child.role == "listitem":
                # Phase 3.1: Check for task list
                task_parts = _task_listitem_parts(child, emit_refs=emit_refs, emit_controls=emit_controls)
                if task_parts:
                    marker, text, control = task_parts
                    rendered = f"{marker} {text}"
                    if emit_controls and control:
                        rendered = f"{rendered} {control}"
                    depth = child.meta.get("list_depth", 0)
                    indent = "  " * depth
                    rendered_items.append(f"{indent}- {rendered}")
                else:
                    text = _inline_text(child.children, emit_refs=emit_refs) or _clean_inline(child.text)
                    if text:
                        depth = child.meta.get("list_depth", 0)
                        indent = "  " * depth
                        rendered_items.append(f"{indent}- {text}")
            else:
                rendered_items.extend(_render_node(child, emit_refs=emit_refs, emit_controls=emit_controls))
        return ["\n".join(rendered_items)] if rendered_items else []

    # Phase 3.4: Image markdown syntax
    if role in _IMAGE_ROLES:
        text = _clean_inline(node.text)
        if not text:
            return []
        url = _node_url(node)
        if url:
            # Phase 3.5: Sanitize URL
            url = _sanitize_display_href(url)
            return [f"![{text}]({url})"]
        else:
            return [f"![{text}]"]

    if role == "/url" or role in _SKIP_SUBTREE_ROLES:
        return []

    # Phase 2.7: Enhanced control rendering
    if role in _CONTROL_ROLES:
        if not emit_controls:
            return []
        return [_render_control(node, emit_refs=emit_refs)]

    if role == "heading":
        text = _heading_text(node)
        if not text:
            return []
        # Phase 2.1: Escape markdown
        text = _escape_md_text(text)
        ref = f" [{node.ref}]" if emit_refs and node.ref else ""
        return [f"{'#' * (node.level or 2)} {text}{ref}"]

    if role == "paragraph":
        text = _inline_text(node.children, emit_refs=emit_refs) or _clean_inline(node.text)
        # Phase 2.1: Escape markdown
        if text:
            text = _escape_md_block_text(text)
        return [text] if text else []

    # Phase 3.3: Blockquote
    if role == "blockquote":
        text = _inline_text(node.children, emit_refs=emit_refs) or _clean_inline(node.text)
        if text:
            lines = text.split("\n")
            return [f"> {line}" for line in lines]
        return []

    if role == "link":
        rendered = _render_link(node, emit_refs=emit_refs)
        return [rendered] if rendered else []

    # Phase 2.3: Enhanced code block rendering
    if role in {"code", "pre"}:
        code = _code_block_text(node)
        if not code:
            return []

        # Phase 1.6: Decode escape sequences
        code = _decode_accessible_string_escapes(code)

        # Phase 1.7: Strip refs from code
        code_lines = [_clean_code_line(line) for line in code.split("\n")]
        code = "\n".join(line for line in code_lines if line or not code_lines)

        # Phase 3.12: Check if substantive
        if not _looks_like_substantive_code_lines(code_lines):
            return []

        # Phase 2.3: Dynamic fence and language
        fence = _code_fence_for(code)
        lang = node.meta.get("language", "")
        fence_line = f"{fence}{lang}" if lang else fence

        return [f"{fence_line}\n{code}\n{fence}"]

    # Phase 3.10: Three-tier table rendering
    if role in {"table", "grid", "treegrid"}:
        return _render_table_enhanced(node, emit_refs=emit_refs)

    if role == "listitem":
        # Phase 3.1: Check for task list
        task_parts = _task_listitem_parts(node, emit_refs=emit_refs, emit_controls=emit_controls)
        if task_parts:
            marker, text, control = task_parts
            rendered = f"{marker} {text}"
            if emit_controls and control:
                rendered = f"{rendered} {control}"
            depth = node.meta.get("list_depth", 0)
            indent = "  " * depth
            return [f"{indent}- {rendered}"]
        else:
            text = _inline_text(node.children, emit_refs=emit_refs) or _clean_inline(node.text)
            if text:
                depth = node.meta.get("list_depth", 0)
                indent = "  " * depth
                return [f"{indent}- {text}"]
            return []

    if role == "row":
        row = _render_row(node, emit_refs=emit_refs)
        return [row] if row else []

    if role in _CONTAINER_ROLES:
        # Containers are structural; their accessible names are usually UI chrome.
        return _render_nodes(node.children, emit_refs=emit_refs, emit_controls=emit_controls)

    if role == "application":
        blocks = [_clean_inline(node.text)] if node.text else []
        blocks.extend(_render_nodes(node.children, emit_refs=emit_refs, emit_controls=emit_controls))
        return [block for block in blocks if block]

    # Phase 2.4: Handle inline formatting roles
    if role in {"strong"}:
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return [f"**{text}**"] if text else []

    if role in {"emphasis", "em", "italic"}:
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return [f"*{text}*"] if text else []

    if role == "deletion":
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return [f"~~{text}~~"] if text else []

    if role in _INLINE_ROLES:
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return [text] if text else []

    if node.children:
        return _render_nodes(node.children, emit_refs=emit_refs, emit_controls=emit_controls)

    text = _clean_inline(node.text)
    return [text] if text else []


# ============================================================================
# Phase 3.1: Task list support
# ============================================================================


def _task_listitem_parts(node: _Item, *, emit_refs: bool, emit_controls: bool) -> Optional[tuple[str, str, str]]:
    """Detect checkbox child and return task list parts.

    Returns: (marker, text, control) or None
    """
    checkbox = next((child for child in node.children if child.role == "checkbox"), None)
    if not checkbox:
        return None

    # Get text from other children
    text_children = [child for child in node.children if child.role != "checkbox"]
    text = _inline_text(text_children, emit_refs=emit_refs) or _clean_inline(node.text)
    if not text:
        return None

    # Check if checked
    checked = _checkbox_checked(checkbox)
    marker = "[x]" if checked else "[ ]"

    # Generate control string if needed
    control = _render_control(checkbox, emit_refs=emit_refs) if emit_controls else ""

    return marker, text, control


def _checkbox_checked(node: _Item) -> bool:
    """Check if a checkbox node is checked."""
    states_lower = {s.lower() for s in node.states}
    if "checked=false" in states_lower or "checked: false" in states_lower:
        return False
    return "checked" in states_lower or "checked=true" in states_lower or "checked: true" in states_lower


# ============================================================================
# Phase 3.10: Three-tier table rendering
# ============================================================================


def _render_table_enhanced(node: _Item, *, emit_refs: bool) -> list[str]:
    """Render table with three-tier system: definition, header, layout."""
    rows = _find_nodes(node, "row")
    if not rows:
        return []

    # Try definition table first (2-column key-value pairs)
    definition_rows = _render_definition_table_rows(node, emit_refs=emit_refs)
    if definition_rows:
        return definition_rows

    # Try header table (markdown table format)
    header_rows = _render_header_table_rows(node, emit_refs=emit_refs)
    if header_rows:
        # Add table label if present
        if node.text:
            label = _clean_inline(node.text)
            if label:
                return [f"**{label}**", ""] + header_rows
        return header_rows

    # Fallback to layout table (definition list format)
    lines = []
    for row in rows:
        rendered = _render_table_row(row, emit_refs=emit_refs)
        if rendered:
            lines.append(rendered)
    return lines if lines else []


def _render_definition_table_rows(node: _Item, *, emit_refs: bool) -> Optional[list[str]]:
    """Render 2-column definition table as **label:** value."""
    rows = _find_nodes(node, "row")
    if not rows:
        return None

    rendered = []
    for row in rows:
        cells = [child for child in row.children if child.role in {"cell", "columnheader", "rowheader", "gridcell"}]
        if len(cells) != 2:
            return None  # Not a 2-column table

        # Skip header rows
        if all(cell.role == "columnheader" for cell in cells):
            continue

        label = _inline_text([cells[0]])
        value = _inline_text([cells[1]])

        if not label or not value:
            return None

        # Check if it looks like a definition (label ends with : or is rowheader)
        is_definition = label.endswith(":") or cells[0].role == "rowheader"
        label = label.rstrip(":").strip()

        if not is_definition or len(label) > 48:
            return None

        rendered.append(f"**{label}:** {value}")

    return rendered if len(rendered) >= 2 else None


def _render_header_table_rows(node: _Item, *, emit_refs: bool) -> Optional[list[str]]:
    """Render table with explicit or inferred headers as markdown table."""
    rows = _find_nodes(node, "row")
    if not rows:
        return None

    # Extract all rows with cells
    table_rows = []
    for row in rows:
        cells = [child for child in row.children if child.role in {"cell", "columnheader", "rowheader", "gridcell"}]
        if not cells:
            continue

        cell_texts = []
        for cell in cells:
            text = _inline_text([cell]) or _clean_inline(cell.text)
            cell_texts.append(text)

        table_rows.append((cells, cell_texts))

    if len(table_rows) < 2:
        return None

    # Check for explicit headers
    has_explicit = node.meta.get("has_explicit_header", False)
    if has_explicit:
        # First row is header
        header_cells, header_texts = table_rows[0]
        data_rows = table_rows[1:]
    else:
        # Check if first row looks like headers
        first_cells, first_texts = table_rows[0]
        if _looks_like_inferred_header(first_texts):
            header_cells, header_texts = first_cells, first_texts
            data_rows = table_rows[1:]
        else:
            return None  # No headers detected

    # Build markdown table
    width = len(header_texts)
    lines = []

    # Header row
    escaped_headers = [_escape_table_cell(t) for t in header_texts]
    lines.append("| " + " | ".join(escaped_headers) + " |")

    # Separator
    lines.append("| " + " | ".join(["---"] * width) + " |")

    # Data rows
    for cells, texts in data_rows:
        # Pad to width
        padded = texts + [""] * (width - len(texts))
        escaped = [_escape_table_cell(t) for t in padded[:width]]
        lines.append("| " + " | ".join(escaped) + " |")

    return lines


def _escape_table_cell(text: str) -> str:
    """Escape pipe characters in table cells."""
    return (text or "").replace("|", "\\|")


def _looks_like_inferred_header(texts: list[str]) -> bool:
    """Check if a row looks like a header (short text, no numbers)."""
    if not texts:
        return False
    for text in texts:
        if not text:
            continue
        # Header cells are typically short and don't look like data
        if len(text) > 40:
            return False
        # Check if it looks like numeric data
        if re.match(r"^\d+\.?\d*$", text.strip()):
            return False
    return True


def _heading_text(node: _Item) -> str:
    non_anchor_children = [child for child in node.children if not _is_direct_anchor_link(child)]
    child_text = _inline_text(non_anchor_children)
    text = child_text or node.text
    # Phase 1.4: Clean heading text
    text = _clean_heading_text(text)
    text = _clean_inline(text)
    return text


def _render_link(node: _Item, *, emit_refs: bool) -> str:
    url = _node_url(node)
    text = _link_text(node)
    if not text or _should_skip_link(text, url, emit_refs=emit_refs):
        return ""

    # Phase 3.11: Filter low-value links
    if not emit_refs and _is_low_value_document_action_link(text):
        return ""

    # Phase 3.5: Sanitize URL
    if url:
        url = _sanitize_display_href(url)
        # Phase 2.1: Escape brackets in link text
        text = _escape_md_link_label(text)
        ref = f" [{node.ref}]" if emit_refs and node.ref else ""
        return f"[{text}]({url}){ref}"
    ref = f" [{node.ref}]" if emit_refs and node.ref else ""
    return f"{text}{ref}"


# Phase 2.7: Enhanced control rendering
def _render_control(node: _Item, *, emit_refs: bool) -> str:
    text = _clean_ui_text(node.text)
    quoted = f'"{text}"' if text else "(unlabeled)"
    ref = f" [{node.ref}]" if emit_refs and node.ref else (" no ref" if emit_refs else "")

    parts = [node.role, quoted]
    if ref:
        parts.append(ref.strip())

    # Add value if present
    if node.value:
        value_clean = _clean_ui_text(node.value)
        parts.append(f'value="{value_clean}"')

    # Add states
    for state in node.states:
        if state:
            parts.append(state)

    return "<" + " ".join(parts) + ">"


def _render_table(node: _Item, *, emit_refs: bool) -> str:
    """Legacy table renderer for backward compatibility."""
    rows = _find_nodes(node, "row")
    lines: list[str] = []
    for row in rows:
        rendered = _render_table_row(row, emit_refs=emit_refs)
        if rendered:
            lines.append(rendered)
    return "\n".join(lines)


def _render_table_row(row: _Item, *, emit_refs: bool) -> str:
    cells = [child for child in row.children if child.role in {"cell", "columnheader", "rowheader", "gridcell"}]
    if cells and all(cell.role == "columnheader" for cell in cells):
        return ""

    if len(cells) >= 2:
        first = _inline_text([cells[0]])
        rest = _clean_inline(" — ".join(filter(None, (_inline_text([cell]) for cell in cells[1:]))))
        if first and rest:
            return f"- {first}: {rest}"
        if first:
            return f"- {first}"

    # Phase 3.15: Handle nested tables
    nested_tables = [child for child in row.children if child.role in {"table", "grid", "treegrid"}]
    if nested_tables:
        lines = []
        for nested in nested_tables:
            lines.extend(_render_table_enhanced(nested, emit_refs=emit_refs))
        if lines:
            return "\n".join(lines)

    text = _inline_text(row.children) or _clean_inline(row.text)
    return f"- {text}" if text else ""


def _render_row(node: _Item, *, emit_refs: bool) -> str:
    return _render_table_row(node, emit_refs=emit_refs)


# ============================================================================
# Inline text
# ============================================================================


def _inline_text(nodes: list[_Item], *, emit_refs: bool = False) -> str:
    fragments: list[str] = []
    for node in nodes:
        fragment = _inline_fragment(node, emit_refs=emit_refs)
        if fragment:
            fragments.append(fragment)
    # Phase 2.5: Smart spacing
    return _format_inline_spacing(fragments)


def _inline_fragment(node: _Item, *, emit_refs: bool = False) -> str:
    role = node.role
    if role == "/url" or role in _CONTROL_ROLES or role in _SKIP_SUBTREE_ROLES:
        return ""
    if role in _IMAGE_ROLES:
        text = _clean_inline(node.text)
        if not text:
            return ""
        url = _node_url(node)
        if url:
            url = _sanitize_display_href(url)
            return f"![{text}]({url})"
        return f"![{text}]"
    if role == "link":
        return _render_link(node, emit_refs=emit_refs)

    # Phase 2.2: Smart inline code
    if role in {"code", "pre"}:
        text = _plain_text(node).strip()
        text = _decode_accessible_string_escapes(text)
        return _inline_code_markdown(text) if text else ""

    # Phase 2.4: Inline formatting
    if role == "strong":
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return f"**{text}**" if text else ""

    if role in {"emphasis", "em", "italic"}:
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return f"*{text}*" if text else ""

    if role == "deletion":
        text = _inline_text(node.children, emit_refs=emit_refs) if node.children else _clean_inline(node.text)
        return f"~~{text}~~" if text else ""

    if role in _INLINE_ROLES or role in _CONTAINER_ROLES or role == "application":
        child_text = _inline_text(node.children, emit_refs=emit_refs) if node.children else ""
        text = child_text or node.text
        return _clean_inline(text)
    if node.children:
        return _inline_text(node.children, emit_refs=emit_refs)
    return _clean_inline(node.text)


# ============================================================================
# Phase 2.3: Code block helpers
# ============================================================================


def _code_block_text(node: _Item) -> str:
    """Extract text from code/pre node, handling line-number gutters."""
    # Phase 3.12: Check for line-number gutter pattern
    row_children = [child for child in node.children if child.role == "row"]
    if row_children:
        # Check if first column is sequential numbers
        rows = []
        for row in row_children:
            cells = [child for child in row.children if child.role in {"cell", "gridcell"}]
            if len(cells) >= 2:
                rows.append(cells)

        if rows and all(len(r) >= 2 for r in rows):
            # Check if first column is sequential numbers
            first_col = [r[0].text.strip() for r in rows]
            if all(str(i + 1) == first_col[i] for i in range(len(first_col))):
                # Extract code from second column
                code_lines = [_plain_text(r[1]) for r in rows]
                return "\n".join(code_lines)

    # Fallback to plain text extraction
    return _plain_text(node)


def _code_fence_for(text: str) -> str:
    """Generate fence with enough backticks to wrap the content."""
    max_run = _max_backtick_run(text)
    return "`" * max(3, max_run + 1)


def _code_language_label(node: _Item) -> str:
    """Extract language from node props or class."""
    # Check props
    class_attr = node.props.get("class", "")
    if class_attr:
        # Look for language-* or lang-* pattern
        match = re.search(r"(?:language|lang)-([a-zA-Z0-9_+.#-]{1,32})", class_attr)
        if match:
            return match.group(1).strip("._-").lower()

    # Check label
    if node.text:
        match = re.match(r"^(?:(?:language|lang)-)?([a-zA-Z0-9_+.#-]{1,32})$", node.text.strip())
        if match:
            return match.group(1).strip("._-").lower()

    return ""


def _looks_like_substantive_code_lines(lines: list[str]) -> bool:
    """Check if code lines look substantive (not just numbers or empty)."""
    nonempty = [line for line in lines if line.strip()]
    if not nonempty:
        return False
    # Check if all lines are just numbers
    if all(re.match(r"^\d+\.?\d*$", line.strip()) for line in nonempty):
        return False
    # Check if any line has code-like characters
    return any(re.search(r"[A-Za-z_{}()[\];=+\-*/<>:'\"`]", line) for line in nonempty)


def _plain_text(node: _Item) -> str:
    fragments: list[str] = []
    if node.text and node.role not in _CONTROL_ROLES and node.role not in _IMAGE_ROLES and node.role != "/url":
        fragments.append(_clean_inline(node.text))
    for child in node.children:
        if child.role in _CONTROL_ROLES or child.role in _IMAGE_ROLES or child.role == "/url":
            continue
        text = _plain_text(child)
        if text:
            fragments.append(text)
    return "\n".join(fragments)


def _link_text(node: _Item) -> str:
    child_text = _inline_text([child for child in node.children if child.role != "/url"])
    text = child_text or node.text
    text = re.sub(r"\s*\(opens in new tab\)\s*", "", text)
    return _clean_inline(text)


def _node_url(node: _Item) -> str:
    for child in node.children:
        if child.role == "/url" and child.url:
            return child.url
    return node.url


def _is_direct_anchor_link(node: _Item) -> bool:
    if node.role != "link":
        return False
    text = _clean_inline(node.text)
    url = _node_url(node)
    return text.startswith("Direct link to ") and url.startswith("#")


def _should_skip_link(text: str, url: str, *, emit_refs: bool = False) -> bool:
    if _is_skip_link_text(text) and url.startswith("#"):
        return True
    if text.startswith("Direct link to ") and url.startswith("#"):
        return True
    if _is_javascript_href(url) and not emit_refs:
        return True
    return False


def _is_skip_link_text(text: str) -> bool:
    return text.lower().startswith("skip to ")


def _is_javascript_href(url: str) -> bool:
    return _clean_url(url).casefold().startswith("javascript:")


# Phase 3.11: Low-value document action links
_LOW_VALUE_DOCUMENT_ACTION_LINKS = {
    "upvote", "hide", "fork", "star", "watch", "subscribe", "sign in", "login",
    "edit this page", "report an issue", "view source",
}


def _is_low_value_document_action_link(text: str) -> bool:
    """Check if link text is a low-value document action."""
    return text.lower().strip() in _LOW_VALUE_DOCUMENT_ACTION_LINKS


# ============================================================================
# Phase 1: Multi-pass pipeline
# ============================================================================


def _join_blocks(blocks: list[str]) -> str:
    """Join blocks with normalization and transforms."""
    # Phase 1.1: Normalize - but preserve block structure
    lines = []
    for block in blocks:
        if block:
            lines.extend(block.split("\n"))
            lines.append("")  # Add blank line after each block

    normalized = _normalize_rendered_lines_preserve_blocks(lines)

    # Phase 1.2: Apply transforms
    transformed = _apply_block_transforms(normalized)

    # Drop preamble before primary heading
    transformed = _drop_preamble_before_primary_heading(transformed)

    # Join
    output = "\n".join(transformed).strip()
    output = re.sub(r"\n{3,}", "\n\n", output)
    return output


def _normalize_rendered_lines_preserve_blocks(lines: list[str]) -> list[str]:
    """Normalize lines while preserving blank line structure between blocks."""
    normalized = []
    previous_blank = False
    in_code_block = False
    code_fence = ""

    for line in lines:
        line = (line or "").rstrip()

        # Track code block boundaries
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                code_fence = line.strip()
            elif line.strip() == code_fence:
                in_code_block = False
                code_fence = ""

        # Inside code blocks, never dedup - just append
        if in_code_block:
            normalized.append(line)
            previous_blank = False
            continue

        if not line:
            if not previous_blank:
                normalized.append("")
            previous_blank = True
            continue

        # Only dedup within same paragraph (no blank line between)
        if normalized and not previous_blank and normalized[-1].lower() == line.lower():
            continue

        normalized.append(line)
        previous_blank = False

    # Trim leading/trailing blanks
    while normalized and not normalized[0]:
        normalized.pop(0)
    while normalized and not normalized[-1]:
        normalized.pop()

    return normalized


def _apply_block_transforms(lines: list[str]) -> list[str]:
    """Apply post-render transforms to lines."""
    transformed = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Drop single-char junk lines
        if line.strip() in {"|", "•", "·", "›", "»"}:
            i += 1
            continue

        # Strip skip-to links
        if re.match(r"^\s*\[Skip to [^\]]+\]\(#[^)]+\)", line, re.IGNORECASE):
            i += 1
            continue

        # Expand dense links
        expanded = _expand_dense_markdown_link_line(line)
        if expanded:
            transformed.extend(expanded)
            i += 1
            continue

        transformed.append(line)
        i += 1

    return transformed


def _expand_dense_markdown_link_line(line: str) -> Optional[list[str]]:
    """Expand lines with 3+ dense markdown links into bullet list."""
    text = (line or "").strip()
    if len(text) < 120:
        return None
    if text.startswith(("- ", "#", "|")) or re.match(r"^\d+\.", text):
        return None

    link_re = re.compile(r"!?\[[^\]\n]+\]\([^\)\n]+\)")
    matches = list(link_re.finditer(text))
    if len(matches) < 3:
        return None

    # Check if there's prose before first link
    first_prefix = text[:matches[0].start()]
    if first_prefix and re.search(r"[A-Za-z]{3,}", first_prefix):
        return None

    # Expand to bullet list
    segments = []
    for idx, match in enumerate(matches):
        start = match.start()
        if idx == 0 and start <= 24:
            start = 0
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        segment = text[start:end].strip(" ,;—")
        if segment:
            segments.append(f"- {segment}")

    return segments if segments else None


def _handle_title(output: str, title: str) -> str:
    """Handle title: prepend if missing, dedup if present."""
    lines = output.split("\n") if output else []

    # Check if title already present
    title_heading = f"# {title.strip()}"
    for line in lines:
        if line.strip().lower() == title_heading.lower():
            return output  # Already present

    # Prepend title
    if lines:
        return f"{title_heading}\n\n{output}"
    return title_heading


# ============================================================================
# Phase 1.4: UI chrome cleaning
# ============================================================================


def _clean_ui_text(text: str) -> str:
    """Clean UI chrome from text."""
    if not text:
        return ""

    text = str(text).strip()
    if not text:
        return ""

    # Strip "Copy code to clipboard"
    text = re.sub(r"\s+Copy code to clipboard\s*$", "", text, flags=re.IGNORECASE)

    # Strip "Direct link to X" pattern
    match = re.match(r"^(?P<head>.+?)\s*Direct link to\s+(?P<target>.+)$", text, re.IGNORECASE)
    if match:
        head = match.group("head").strip()
        target = match.group("target").strip()
        if head and target and head.lower() == target.lower():
            text = head

    # Strip "Link for X" pattern
    match = re.match(r"^(?P<head>.+?)\s*Link for\s+(?P<target>.+)$", text, re.IGNORECASE)
    if match:
        head = match.group("head").strip()
        target = match.group("target").strip()
        if head and target and head.lower() == target.lower():
            text = head

    return text


def _clean_heading_text(text: str) -> str:
    """Clean heading text, removing anchor links."""
    text = _clean_ui_text(text)
    if not text:
        return ""

    # Strip "Go to slug" pattern
    match = re.match(r"^(?P<head>.+?)\s*Go to\s+(?P<target>[a-z0-9][a-z0-9-]{1,80})$", text, re.IGNORECASE)
    if match:
        head = match.group("head").strip()
        target = match.group("target").lower()
        slug = re.sub(r"[^a-z0-9]+", "-", head.lower()).strip("-")
        if head and target and (slug == target or target in slug.split("-")):
            text = head

    return text


def _clean_code_line(line: str) -> str:
    """Clean a code line by stripping refs and UI chrome."""
    line = re.sub(r"\s*\[(?:ref=)?e\d+\]\s*", " ", line)
    line = re.sub(r"\s*\[nth=\d+\]\s*", " ", line)
    line = re.sub(r"\s*\[cursor=pointer\]\s*", " ", line)
    line = re.sub(r"\s+Copy code to clipboard\s*$", "", line, flags=re.IGNORECASE)
    return line.rstrip()


# ============================================================================
# Phase 2: Markdown safety
# ============================================================================


def _escape_md_text(text: str) -> str:
    """Escape markdown syntax at the start of text."""
    if not text:
        return text

    # Escape leading markdown syntax
    if text[0] in {"#", ">"}:
        return "\\" + text
    if text.startswith(("- ", "* ", "+ ")):
        return "\\" + text
    if re.match(r"^\d+[.)]\s", text):
        return "\\" + text
    if text in {"---", "***", "___"}:
        return "\\" + text

    return text


def _escape_md_block_text(text: str) -> str:
    """Escape markdown syntax including table pipes."""
    escaped = _escape_md_text(text)
    if escaped == text and text.startswith("|"):
        return "\\" + text
    return escaped


def _escape_md_link_label(text: str) -> str:
    """Escape brackets in link text."""
    return (text or "").replace("[", "\\[").replace("]", "\\]")


def _max_backtick_run(text: str) -> int:
    """Find the longest run of backticks in text."""
    return max((len(m.group(0)) for m in re.finditer(r"`+", text or "")), default=0)


def _inline_code_markdown(text: str) -> str:
    """Wrap text in backticks, using enough to not conflict."""
    if not text:
        return ""
    run = _max_backtick_run(text)
    ticks = "`" * max(1, run + 1)
    if run:
        return f"{ticks} {text} {ticks}"
    return f"{ticks}{text}{ticks}"


# Phase 2.5: Smart inline spacing
def _format_inline_spacing(parts: list[str]) -> str:
    """Format inline fragments with proper spacing."""
    if not parts:
        return ""

    result = ""
    no_space_before = set(".,;:!?)]}…")
    no_space_after = set("([{¿¡")

    for raw_part in parts:
        part = _clean_inline(raw_part)
        if not part:
            continue

        if not result:
            result = part
            continue

        # Check if we need space
        if part[0] in no_space_before or result[-1] in no_space_after:
            result += part
        else:
            result += " " + part

    return result.strip()


# ============================================================================
# Phase 3.5: URL sanitization
# ============================================================================


def _sanitize_display_href(href: str) -> str:
    """Remove tracking parameters from URLs."""
    raw = href or ""
    if not raw or "?" not in raw:
        return raw

    try:
        parsed = urlparse(raw)
        params = parse_qs(parsed.query, keep_blank_values=True)

        # Filter out tracking params
        filtered = {}
        changed = False
        for key, values in params.items():
            key_lower = key.lower()
            if key_lower.startswith("utm_") or key_lower in _TRACKING_QUERY_KEYS:
                changed = True
                continue
            filtered[key] = values

        if not changed:
            return raw

        # Rebuild query string
        new_query = urlencode(filtered, doseq=True)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)

    except Exception:
        return raw


# ============================================================================
# Cleanup helpers
# ============================================================================


def _drop_preamble_before_primary_heading(blocks: list[str]) -> list[str]:
    for idx, block in enumerate(blocks):
        if block.startswith("# "):
            return blocks[idx:]
    return blocks


def _clean_inline(text: str) -> str:
    text = _strip_refs(str(text or ""))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if _is_private_use_symbol_junk(text):
        return ""
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = text.replace(") .", ").")
    text = text.replace("] .", "].")
    text = text.replace("` .", "`.")
    return text.strip()


def _is_private_use_symbol_junk(text: str) -> bool:
    compact = "".join(ch for ch in (text or "") if not ch.isspace())
    if not compact:
        return False
    return all(
        "\ue000" <= ch <= "\uf8ff"
        or "\U000f0000" <= ch <= "\U000ffffd"
        or "\U00100000" <= ch <= "\U0010fffd"
        for ch in compact
    )


def _clean_url(url: str) -> str:
    url = str(url or "").strip()
    if (url.startswith('"') and url.endswith('"')) or (url.startswith("'") and url.endswith("'")):
        url = url[1:-1]
    return url.strip()


def _strip_refs(text: str) -> str:
    """Strip ref annotations, preserving numeric citations."""
    return _REF_RE.sub("", text).strip()
