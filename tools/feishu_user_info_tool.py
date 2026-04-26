"""Feishu User Info Tool -- retrieve current user info via Feishu/Lark API.

Provides ``feishu_get_my_user_info`` for fetching the authenticated user's
basic profile using a user_access_token (UAT).
Uses the same lazy-import + BaseRequest pattern as existing tools.
The lark client is injected per-thread by the comment event handler.
"""

import json
import logging
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


def _check_feishu():
    try:
        import lark_oapi  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# feishu_get_my_user_info
# ---------------------------------------------------------------------------

_USER_INFO_URI = "/open-apis/authen/v1/user_info"

FEISHU_GET_MY_USER_INFO_SCHEMA = {
    "name": "feishu_get_my_user_info",
    "description": (
        "Get the current authenticated user's basic info via user_access_token. "
        "Returns name, avatar, email, mobile, and open_id of the token owner."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}


def _handle_feishu_get_my_user_info(args: dict, **kwargs) -> str:
    """Handler for feishu_get_my_user_info tool.

    Fetches the current user's profile using the UAT from disk via
    FeishuClient.for_user(). No additional parameters needed.

    Args:
        args: Tool arguments (unused — no parameters).
        **kwargs: Additional keyword arguments.

    Returns:
        JSON string (tool_error or tool_result).
    """
    try:
        from tools.feishu_oapi_client import FeishuClient, NeedAuthorizationError
    except ImportError:
        return tool_error("feishu_oapi_client not available")

    try:
        fc = FeishuClient.for_user()
    except NeedAuthorizationError as exc:
        return tool_error(f"UAT not available: {exc}")
    except ValueError as exc:
        return tool_error(f"Feishu client config error: {exc}")

    try:
        from lark_oapi import AccessTokenType, RequestOption
        from lark_oapi.core.enum import HttpMethod
        from lark_oapi.core.model.base_request import BaseRequest
    except ImportError:
        return tool_error("lark_oapi not installed")

    request = (
        BaseRequest.builder()
        .http_method(HttpMethod.GET)
        .uri(_USER_INFO_URI)
        .token_types({AccessTokenType.USER})
        .build()
    )

    opt = (
        RequestOption.builder()
        .user_access_token(fc.access_token)
        .build()
    )

    response = fc.sdk.request(request, opt)

    code = getattr(response, "code", None)
    msg = getattr(response, "msg", "")

    # Try raw.content first
    data: dict = {}
    raw = getattr(response, "raw", None)
    if raw and hasattr(raw, "content"):
        try:
            body_json = json.loads(raw.content)
            if code is None:
                code = body_json.get("code", -1)
            if not msg:
                msg = body_json.get("msg", "")
            data = body_json.get("data", {})
        except (json.JSONDecodeError, AttributeError):
            pass

    if code != 0:
        logger.error("feishu_get_my_user_info failed: code=%s msg=%s", code, msg)
        return tool_error(f"Get user info failed: code={code} msg={msg}")

    if not data:
        resp_data = getattr(response, "data", None)
        if isinstance(resp_data, dict):
            data = resp_data
        elif resp_data and hasattr(resp_data, "__dict__"):
            data = vars(resp_data)

    logger.info("feishu_get_my_user_info: fetched user open_id=%s", data.get("open_id", ""))
    return tool_result(success=True, data=data)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="feishu_get_my_user_info",
    toolset="feishu_user_info",
    schema=FEISHU_GET_MY_USER_INFO_SCHEMA,
    handler=_handle_feishu_get_my_user_info,
    check_fn=_check_feishu,
    requires_env=[],
    is_async=False,
    description="Get current user info via UAT",
    emoji="\U0001f464",
)
