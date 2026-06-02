"""
Skill Permission Gate - Hermes Agent 权限控制插件
功能：
1. 只有管理员可以创建/编辑/删除 skill
2. 非管理员调用 skill_manage 时自动拦截
3. 对 skill 目录和配置文件的写入操作进行权限控制
4. 发送飞书消息卡片审批支持
"""
import os
import sys
import json
import logging
from pathlib import Path

# 从 session context 获取用户信息
try:
    from gateway.session_context import get_session_env
except ImportError:
    get_session_env = lambda key, default="": default

logger = logging.getLogger(__name__)

# ============== 配置区域 ==============
# 管理员用户 ID 白名单
# 用 /whoami 命令获取你的飞书用户 ID
ADMIN_USER_IDS = {
    "ou_7dd542da96710c66adaf2a4fd37290fd",  # 小高的飞书用户 ID
}

# 需要审批的 skill 写操作
WRITE_ACTIONS = {"create", "edit", "patch", "delete", "write_file", "remove_file"}

# 敏感目录（不允许非管理员写入
SENSITIVE_PATHS = [
    str(Path.home() / ".hermes" / "skills"),
    str(Path.home() / ".hermes" / "config.yaml"),
    str(Path.home() / ".hermes" / ".env"),
    str(Path.home() / ".hermes" / "plugins"),
]

# 审批通知接收人（审批消息发给谁
APPROVAL_RECEIVER = "ou_7dd542da96710c66adaf2a4fd37290fd"
# ======================================


def _get_current_user_id() -> str:
    """获取当前会话的用户 ID"""
    try:
        # 从 session 环境变量获取
        user_id = get_session_env("HERMES_USER_ID", "")
        if user_id:
            return user_id
        
        # 备用方式：从 context vars 获取
        import contextvars
        ctx_user = contextvars.ContextVar("user_id", default="")
        return ctx_user.get("")
    except Exception:
        return ""


def _is_sensitive_path(path: str) -> bool:
    """检查路径是否属于敏感目录"""
    try:
        path = os.path.expanduser(path)
        path = str(Path(path).resolve())
        return any(path.startswith(p) or p in path for p in SENSITIVE_PATHS)
    except Exception:
        return False


def _send_approval_card(tool_name: str, args: dict, user_id: str) -> None:
    """发送飞书审批消息卡片给管理员"""
    try:
        import httpx
        
        # 从环境变量获取飞书凭证
        app_id = os.getenv("FEISHU_APP_ID", "")
        app_secret = os.getenv("FEISHU_APP_SECRET", "")
        
        if not app_id or not app_secret:
            logger.warning("未配置飞书 APP 凭证，无法发送审批卡片")
            return
        
        # 获取 tenant_access_token
        token_url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        resp = httpx.post(token_url, json={
            "app_id": app_id,
            "app_secret": app_secret
        }, timeout=10)
        
        if resp.status_code != 200:
            logger.error(f"获取飞书 token 失败: {resp.text}")
            return
        
        token_data = resp.json()
        if token_data.get("code") != 0:
            logger.error(f"飞书 token 错误: {token_data}")
            return
        
        access_token = token_data["tenant_access_token"]
        
        # 构建审批卡片内容
        action = args.get("action", "unknown")
        skill_name = args.get("name", "unknown")
        
        # 格式化参数显示
        args_preview = json.dumps(args, ensure_ascii=False, indent=2)
        if len(args_preview) > 500:
            args_preview = args_preview[:500] + "\n... (内容过长已截断)"
        
        # 发送消息卡片
        msg_url = "https://open.feishu.cn/open-apis/im/v1/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        card_content = {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🔐 Skill 创建审批请求"
                },
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**用户请求操作 Skill，需要您审批：\n\n"
                                  f"**操作用户**: `{user_id}`\n"
                                  f"**操作类型**: `{action}`\n"
                                  f"**Skill 名称**: `{skill_name}`\n"
                                  f"**工具名称**: `{tool_name}`"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**操作参数详情：\n```json\n{args_preview}\n```"
                    }
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "✅ 批准"
                            },
                            "type": "primary",
                            "value": {
                                "action": "approve_skill",
                                "tool_name": tool_name,
                                "user_id": user_id
                            }
                        },
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "❌ 拒绝"
                            },
                            "type": "danger",
                            "value": {
                                "action": "deny_skill",
                                "tool_name": tool_name,
                                "user_id": user_id
                            }
                        }
                    ]
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": "💡 点击按钮后，系统会自动执行对应操作。批准后 skill 将继续执行，拒绝后将终止操作。"
                        }
                    ]
                }
            ]
        }
        
        payload = {
            "receive_id": APPROVAL_RECEIVER,
            "msg_type": "interactive",
            "content": json.dumps(card_content, ensure_ascii=False)
        }
        
        resp = httpx.post(
            f"{msg_url}?receive_id_type=open_id",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            result = resp.json()
            if result.get("code") == 0:
                logger.info(f"审批卡片已发送给管理员 {APPROVAL_RECEIVER}")
            else:
                logger.error(f"发送审批卡片失败: {result}")
        else:
            logger.error(f"发送审批卡片 HTTP 错误: {resp.status_code} - {resp.text}")
            
    except Exception as e:
        logger.error(f"发送审批卡片异常: {str(e)}", exc_info=True)


def pre_tool_call(tool_name: str, args: dict, task_id: str, **kwargs):
    """
    在任何工具执行前拦截
    
    返回 None = 放行
    返回 {"block": True, "message": "..."} = 拦截并提示
    """
    user_id = _get_current_user_id()
    logger.info(f"[Skill Permission Gate] tool=%s, user=%s, task=%s", 
                tool_name, user_id, task_id)
    
    # 管理员直接放行
    if user_id in ADMIN_USER_IDS:
        logger.info(f"[Skill Permission Gate] 管理员 {user_id} 操作，放行")
        return None
    
    # 匿名用户无法识别时记录日志但继续（CLI 模式）
    if not user_id:
        logger.warning("[Skill Permission Gate] 无法识别用户 ID")
    
    # ========== 拦截 skill_manage 的写操作 ==========
    if tool_name == "skill_manage":
        action = args.get("action", "")
        if action in WRITE_ACTIONS:
            skill_name = args.get("name", "unknown")
            
            # 发送审批卡片给管理员
            _send_approval_card(tool_name, args, user_id)
            
            logger.warning(f"[Skill Permission Gate] 拦截非管理员 skill_{action} 操作: {skill_name}")
            return {
                "block": True,
                "message": f"⚠️ **权限不足**\n\n"
                          f"只有管理员可以执行 skill_{action} 操作。\n"
                          f"已发送审批请求给管理员，请等待审批。\n\n"
                          f"操作用户: `{user_id}`\n"
                          f"操作类型: `{action}`\n"
                          f"Skill 名称: `{skill_name}`"
            }
    
    # ========== 拦截对敏感目录的直接写入 ==========
    if tool_name in {"write_file", "patch"}:
        path = args.get("path", "")
        if _is_sensitive_path(path):
            logger.warning(f"[Skill Permission Gate] 拦截非管理员写入敏感路径: {path}")
            return {
                "block": True,
                "message": f"⚠️ **权限不足**\n\n"
                          f"只有管理员可以修改配置和 skill 文件。\n\n"
                          f"目标路径: `{path}`\n"
                          f"操作用户: `{user_id}`"
            }
    
    # 其他操作放行
    return None


def register(ctx):
    """插件注册入口"""
    ctx.register_hook("pre_tool_call", pre_tool_call)
    logger.info("✅ Skill Permission Gate 插件已加载")
    logger.info(f"   管理员白名单: {ADMIN_USER_IDS}")
    logger.info(f"   审批接收人: {APPROVAL_RECEIVER}")
