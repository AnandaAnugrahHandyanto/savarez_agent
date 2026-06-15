import os
import sys
from mcp.server.fastmcp import FastMCP

# 初始化 MCP 服务
mcp = FastMCP("Hermes-Bridge")

@mcp.tool()
def read_script(path: str) -> str:
    """读取本地的漫剧脚本文件"""
    # 自动补全路径，方便你在 Trae 里直接传文件名
    full_path = os.path.expanduser(path)
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

@mcp.tool()
def save_refined_script(path: str, content: str) -> str:
    """将洗好的爆款脚本保存到本地"""
    full_path = os.path.expanduser(path)
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已成功保存至: {path}"

@mcp.tool()
def list_scripts() -> list:
    """列出当前目录下的所有脚本"""
    return [f for f in os.listdir(".") if f.endswith((".txt", ".md"))]

if __name__ == "__main__":
    mcp.run()
