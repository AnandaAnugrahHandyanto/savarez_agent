#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QMT 智能推送系统依赖安装
"""

import subprocess
import sys

REQUIRED_PACKAGES = [
    "requests",  # HTTP 请求
    "akshare",  # 免费行情数据
]

OPTIONAL_PACKAGES = {
    "tushare": "历史数据（需要 token）",
    "openai": "OpenAI LLM",
    "anthropic": "Anthropic Claude LLM",
}

def install_package(package: str):
    """安装 Python 包"""
    print(f"安装 {package}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            check=True,
            capture_output=True,
        )
        print(f"✓ {package} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {package} 安装失败: {e.stderr.decode()}")
        return False

def check_package(package: str) -> bool:
    """检查包是否已安装"""
    try:
        __import__(package)
        return True
    except ImportError:
        return False

def main():
    print("=" * 60)
    print("QMT 智能推送系统依赖安装")
    print("=" * 60)
    
    # 必需包
    print("\n=== 必需包 ===")
    for package in REQUIRED_PACKAGES:
        if check_package(package):
            print(f"✓ {package} 已安装")
        else:
            install_package(package)
    
    # 可选包
    print("\n=== 可选包 ===")
    for package, description in OPTIONAL_PACKAGES.items():
        if check_package(package):
            print(f"✓ {package} 已安装 ({description})")
        else:
            print(f"- {package} 未安装 ({description})")
            response = input(f"  是否安装 {package}? [y/N]: ")
            if response.lower() == "y":
                install_package(package)
    
    print("\n" + "=" * 60)
    print("依赖安装完成")
    print("=" * 60)
    
    # 测试
    print("\n=== 测试数据源 ===")
    try:
        from qmt_data_source import get_data_source
        source = get_data_source("auto")
        print(f"✓ 数据源可用: {source.__class__.__name__}")
    except Exception as e:
        print(f"✗ 数据源不可用: {e}")
    
    print("\n=== 测试 LLM ===")
    try:
        from llm_client import get_llm_client
        client = get_llm_client("auto")
        print(f"✓ LLM 可用: {client.__class__.__name__}")
    except Exception as e:
        print(f"✗ LLM 不可用: {e}")
    
    print("\n配置指南: ~/.hermes/runtime-hermes-agent/QMT_CONFIG_GUIDE.md")

if __name__ == "__main__":
    main()
