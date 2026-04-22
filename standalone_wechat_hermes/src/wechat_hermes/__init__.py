"""Standalone WeChat (iLink) bridge extracted from Hermes Agent."""

from wechat_hermes.weixin_adapter import WeixinAdapter, check_weixin_requirements
from wechat_hermes.base_platform import MessageEvent, MessageType, SendResult
from wechat_hermes.gateway_config import Platform, PlatformConfig

__all__ = [
    "WeixinAdapter",
    "check_weixin_requirements",
    "MessageEvent",
    "MessageType",
    "SendResult",
    "Platform",
    "PlatformConfig",
]
