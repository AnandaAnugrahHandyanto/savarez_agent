"""Feishu Document Tool -- read and create documents via Feishu/Lark API.

Provides:
- feishu_doc_read: read document content as plain text
- feishu_doc_create: create a new empty document (returns URL)
- feishu_doc_write: write markdown-like content to a document

Uses the official lark_oapi SDK (docx.v1 service).
"""

import json
import logging
import os
import re
import threading

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# Thread-local storage for the lark client injected by feishu_comment handler.
_local = threading.local()


def set_client(client):
    """Store a lark client for the current thread (called by feishu_comment)."""
    _local.client = client


def get_client():
    """Return the lark client for the current thread, or None."""
    return getattr(_local, "client", None)


def _get_or_create_client():
    """Get existing client or create one from env vars."""
    client = get_client()
    if client is not None:
        return client, None

    app_id = os.environ.get("FEISHU_APP_ID", "").strip()
    app_secret = os.environ.get("FEISHU_APP_SECRET", "").strip()
    if not app_id or not app_secret:
        return None, "Feishu client not available and FEISHU_APP_ID/FEISHU_APP_SECRET not set"

    try:
        import lark_oapi as lark
        client = (
            lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(lark.LogLevel.WARNING)
            .build()
        )
        return client, None
    except Exception as e:
        return None, f"Failed to create Feishu client: {e}"


def _check_feishu():
    try:
        import lark_oapi  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# feishu_doc_read
# ---------------------------------------------------------------------------

_RAW_CONTENT_URI = "/open-apis/docx/v1/documents/:document_id/raw_content"

FEISHU_DOC_READ_SCHEMA = {
    "name": "feishu_doc_read",
    "description": (
        "Read the full content of a Feishu/Lark document as plain text. "
        "Useful when you need more context beyond the quoted text in a comment."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc_token": {
                "type": "string",
                "description": "The document token (from the document URL or comment context).",
            },
        },
        "required": ["doc_token"],
    },
}


def _handle_feishu_doc_read(args: dict, **kwargs) -> str:
    doc_token = args.get("doc_token", "").strip()
    if not doc_token:
        return tool_error("doc_token is required")

    client = get_client()
    if client is None:
        return tool_error("Feishu client not available (not in a Feishu comment context)")

    try:
        from lark_oapi import AccessTokenType
        from lark_oapi.core.enum import HttpMethod
        from lark_oapi.core.model.base_request import BaseRequest
    except ImportError:
        return tool_error("lark_oapi not installed")

    request = (
        BaseRequest.builder()
        .http_method(HttpMethod.GET)
        .uri(_RAW_CONTENT_URI)
        .token_types({AccessTokenType.TENANT})
        .paths({"document_id": doc_token})
        .build()
    )

    response = client.request(request)

    code = getattr(response, "code", None)
    if code != 0:
        msg = getattr(response, "msg", "unknown error")
        return tool_error(f"Failed to read document: code={code} msg={msg}")

    raw = getattr(response, "raw", None)
    if raw and hasattr(raw, "content"):
        try:
            body = json.loads(raw.content)
            content = body.get("data", {}).get("content", "")
            return tool_result(success=True, content=content)
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: try response.data
    data = getattr(response, "data", None)
    if data:
        if isinstance(data, dict):
            content = data.get("content", "")
        else:
            content = getattr(data, "content", str(data))
        return tool_result(success=True, content=content)

    return tool_error("No content returned from document API")


# ---------------------------------------------------------------------------
# feishu_doc_create
# ---------------------------------------------------------------------------

FEISHU_DOC_CREATE_SCHEMA = {
    "name": "feishu_doc_create",
    "description": (
        "Create a new Feishu/Lark document. Returns the document URL and ID. "
        "Supports optional folder_token to specify location."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Document title (optional).",
            },
            "folder_token": {
                "type": "string",
                "description": "Folder token. Empty = root directory.",
            },
        },
        "required": [],
    },
}


def _handle_feishu_doc_create(args: dict, **kwargs) -> str:
    title = args.get("title", "").strip() or None
    folder_token = args.get("folder_token", "").strip() or None

    client, error = _get_or_create_client()
    if client is None:
        return tool_error(error)

    try:
        from lark_oapi.api.docx.v1 import CreateDocumentRequest, CreateDocumentRequestBody
    except ImportError:
        return tool_error("lark_oapi docx module not available")

    try:
        body_builder = CreateDocumentRequestBody.builder()
        if title:
            body_builder = body_builder.title(title)
        if folder_token:
            body_builder = body_builder.folder_token(folder_token)

        request = CreateDocumentRequest.builder().request_body(body_builder.build()).build()
        response = client.docx.v1.document.create(request)

        if not response.success():
            return tool_error(f"Failed to create document: code={response.code} msg={response.msg}")

        doc = response.data.document
        doc_id = doc.document_id
        url = f"https://feishu.cn/docx/{doc_id}"
        return tool_result(
            success=True,
            document_id=doc_id,
            url=url,
            title=doc.title,
            content=f"Document created: {doc.title}\nURL: {url}\nID: {doc_id}",
        )
    except Exception as e:
        return tool_error(f"Failed to create document: {e}")


# ---------------------------------------------------------------------------
# feishu_doc_write
# ---------------------------------------------------------------------------

FEISHU_DOC_WRITE_SCHEMA = {
    "name": "feishu_doc_write",
    "description": (
        "Write content to a Feishu/Lark document. Accepts markdown-like text. "
        "Supports headings (# ## ###), bullet lists (- item), and plain text paragraphs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "doc_id": {
                "type": "string",
                "description": "The document ID (from feishu_doc_create).",
            },
            "content": {
                "type": "string",
                "description": "Content in markdown format. Supports # ## ### headings, - bullet lists, and plain paragraphs.",
            },
        },
        "required": ["doc_id", "content"],
    },
}


def _parse_markdown_to_blocks(markdown_text: str) -> list:
    """Parse markdown text into Feishu block objects."""
    from lark_oapi.api.docx.v1 import Block, TextElement, TextRun

    blocks = []
    lines = markdown_text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # Headings
        if stripped.startswith("# "):
            text = stripped[2:].strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(3).heading1(elements).build())
        elif stripped.startswith("## "):
            text = stripped[3:].strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(4).heading2(elements).build())
        elif stripped.startswith("### "):
            text = stripped[4:].strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(5).heading3(elements).build())
        elif stripped.startswith("#### "):
            text = stripped[5:].strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(6).heading4(elements).build())
        # Bullet list
        elif stripped.startswith("- "):
            text = stripped[2:].strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(12).bullet(elements).build())
        # Ordered list
        elif re.match(r"^\d+\.\s", stripped):
            text = re.sub(r"^\d+\.\s", "", stripped).strip()
            elements = [TextElement.builder().text_run(TextRun.builder().content(text).build()).build()]
            blocks.append(Block.builder().block_type(13).ordered(elements).build())
        # Horizontal rule
        elif stripped in ("---", "***", "___"):
            blocks.append(Block.builder().block_type(22).build())
        # Code block (skip content for now, treat as text)
        elif stripped.startswith("```"):
            # Skip code block content
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_line = lines[i]
                elements = [TextElement.builder().text_run(TextRun.builder().content(code_line).build()).build()]
                blocks.append(Block.builder().block_type(14).code(elements).build())
                i += 1
        # Table (skip - complex to render)
        elif stripped.startswith("|"):
            # Collect table lines and render as text
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            table_text = "\n".join(table_lines)
            elements = [TextElement.builder().text_run(TextRun.builder().content(table_text).build()).build()]
            blocks.append(Block.builder().block_type(2).text(elements).build())
            continue
        # Regular paragraph
        else:
            elements = [TextElement.builder().text_run(TextRun.builder().content(stripped).build()).build()]
            blocks.append(Block.builder().block_type(2).text(elements).build())

        i += 1

    return blocks


def _handle_feishu_doc_write(args: dict, **kwargs) -> str:
    doc_id = args.get("doc_id", "").strip()
    content = args.get("content", "").strip()

    if not doc_id:
        return tool_error("doc_id is required")
    if not content:
        return tool_error("content is required")

    client, error = _get_or_create_client()
    if client is None:
        return tool_error(error)

    try:
        from lark_oapi.api.docx.v1 import (
            CreateDocumentBlockChildrenRequest,
            CreateDocumentBlockChildrenRequestBody,
        )
    except ImportError:
        return tool_error("lark_oapi docx module not available")

    try:
        blocks = _parse_markdown_to_blocks(content)
        if not blocks:
            return tool_error("No valid blocks parsed from content")

        # Write in batches of 50 (API limit)
        batch_size = 50
        total_written = 0
        for start in range(0, len(blocks), batch_size):
            batch = blocks[start:start + batch_size]
            request = (
                CreateDocumentBlockChildrenRequest.builder()
                .document_id(doc_id)
                .block_id(doc_id)
                .request_body(
                    CreateDocumentBlockChildrenRequestBody.builder()
                    .children(batch)
                    .build()
                )
                .build()
            )
            response = client.docx.v1.document_block_children.create(request)
            if not response.success():
                return tool_error(f"Failed to write blocks: code={response.code} msg={response.msg}")
            total_written += len(batch)

        url = f"https://feishu.cn/docx/{doc_id}"
        return tool_result(
            success=True,
            document_id=doc_id,
            url=url,
            blocks_written=total_written,
            content=f"Written {total_written} blocks to document\nURL: {url}",
        )
    except Exception as e:
        return tool_error(f"Failed to write document: {e}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="feishu_doc_read",
    toolset="feishu_doc",
    schema=FEISHU_DOC_READ_SCHEMA,
    handler=_handle_feishu_doc_read,
    check_fn=_check_feishu,
    requires_env=[],
    is_async=False,
    description="Read Feishu document content",
    emoji="\U0001f4c4",
)

registry.register(
    name="feishu_doc_create",
    toolset="feishu_doc",
    schema=FEISHU_DOC_CREATE_SCHEMA,
    handler=_handle_feishu_doc_create,
    check_fn=_check_feishu,
    requires_env=[],
    is_async=False,
    description="Create Feishu document",
    emoji="\U0001f4dd",
)

registry.register(
    name="feishu_doc_write",
    toolset="feishu_doc",
    schema=FEISHU_DOC_WRITE_SCHEMA,
    handler=_handle_feishu_doc_write,
    check_fn=_check_feishu,
    requires_env=[],
    is_async=False,
    description="Write content to Feishu document",
    emoji="\u270f\ufe0f",
)
