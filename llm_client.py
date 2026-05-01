#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM API 适配器
支持 OpenAI、Anthropic、本地 Ollama 等
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, List

HERMES_HOME = Path.home() / ".hermes"


class LLMClient:
    """LLM 客户端基类"""
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        """
        聊天接口
        
        messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        raise NotImplementedError
    
    def analyze_news(self, news_title: str, news_content: Optional[str] = None) -> dict:
        """分析新闻（专用接口）"""
        prompt = f"""你是A股短线交易专家，请分析以下新闻对股市的影响：

标题：{news_title}
"""
        
        if news_content:
            prompt += f"\n内容：{news_content[:500]}\n"
        
        prompt += """
请以 JSON 格式返回分析结果：
{
    "sentiment": "利好/利空/中性",
    "strength": 1-10 (影响强度),
    "related_sectors": ["相关板块"],
    "related_stocks": ["相关个股"],
    "duration": "1日/3日/周级/月级 (持续性)",
    "catalyst_score": 0-10 (作为一进二催化剂的评分),
    "summary": "一句话总结",
    "reasoning": "分析理由"
}

评分标准：
- strength: 政策/重大事件 8-10，行业动态 5-7，一般消息 1-4
- catalyst_score: 直接利好个股 8-10，板块利好 5-7，间接影响 1-4
- duration: 政策/产业趋势为周级/月级，事件驱动为1日/3日

只返回 JSON，不要其他内容。
"""
        
        messages = [{"role": "user", "content": prompt}]
        response = self.chat(messages, temperature=0.3, max_tokens=1000)
        
        # 提取 JSON
        try:
            # 尝试直接解析
            return json.loads(response)
        except:
            # 尝试提取 JSON 块
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                raise ValueError(f"无法解析 LLM 响应: {response}")


class OpenAIClient(LLMClient):
    """OpenAI API 客户端"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", base_url: Optional[str] = None):
        self.api_key = api_key or self._load_api_key()
        self.model = model
        self.base_url = base_url
        
        if not self.api_key:
            raise ValueError("OpenAI API key 未配置")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")
    
    def _load_api_key(self) -> Optional[str]:
        """从配置文件或环境变量加载 API key"""
        # 优先从环境变量
        if "OPENAI_API_KEY" in os.environ:
            return os.environ["OPENAI_API_KEY"]
        
        # 从配置文件
        config_file = HERMES_HOME / "config" / "openai.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("api_key")
        
        return None
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content


class AnthropicClient(LLMClient):
    """Anthropic Claude API 客户端"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or self._load_api_key()
        self.model = model
        
        if not self.api_key:
            raise ValueError("Anthropic API key 未配置")
        
        try:
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")
    
    def _load_api_key(self) -> Optional[str]:
        if "ANTHROPIC_API_KEY" in os.environ:
            return os.environ["ANTHROPIC_API_KEY"]
        
        config_file = HERMES_HOME / "config" / "anthropic.json"
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("api_key")
        
        return None
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        # 转换消息格式（Anthropic 不支持 system role 在 messages 中）
        system_message = None
        user_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                user_messages.append(msg)
        
        kwargs = {
            "model": self.model,
            "messages": user_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        if system_message:
            kwargs["system"] = system_message
        
        response = self.client.messages.create(**kwargs)
        return response.content[0].text


class OllamaClient(LLMClient):
    """本地 Ollama 客户端"""
    
    def __init__(self, model: str = "qwen2.5:14b", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        
        try:
            import requests
            self.requests = requests
        except ImportError:
            raise ImportError("请安装 requests: pip install requests")
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }
        
        response = self.requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        return data["message"]["content"]


class RuleBasedFallback(LLMClient):
    """规则引擎 Fallback（当 LLM 不可用时）"""
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 2000) -> str:
        # 简单回复
        return "规则引擎 fallback，无法生成智能回复"
    
    def analyze_news(self, news_title: str, news_content: Optional[str] = None) -> dict:
        """基于规则的新闻分析"""
        text = (news_title + " " + (news_content or "")).lower()
        
        sentiment = "中性"
        strength = 5
        related_sectors = []
        related_stocks = []
        duration = "1日"
        catalyst_score = 5.0
        
        # 利好关键词
        if any(kw in text for kw in ["利好", "上涨", "增长", "突破", "订单", "中标", "政策支持", "补贴", "减税"]):
            sentiment = "利好"
            strength = 7
            catalyst_score = 7.0
        
        # 利空关键词
        if any(kw in text for kw in ["利空", "下跌", "亏损", "风险", "调查", "处罚", "限制", "禁止"]):
            sentiment = "利空"
            strength = 7
            catalyst_score = 3.0
        
        # 政策类
        if any(kw in text for kw in ["政策", "国务院", "发改委", "工信部", "央行", "证监会"]):
            strength = 9
            duration = "周级"
            catalyst_score = 8.0
        
        # 板块识别
        sector_keywords = {
            "AI算力": ["算力", "gpu", "服务器", "数据中心", "液冷"],
            "半导体": ["芯片", "半导体", "晶圆", "封测"],
            "新能源": ["新能源", "锂电", "电池", "充电桩"],
            "医药": ["医药", "创新药", "医疗器械"],
            "低空经济": ["低空", "飞行汽车", "evtol", "通用航空"],
        }
        
        for sector, keywords in sector_keywords.items():
            if any(kw in text for kw in keywords):
                related_sectors.append(sector)
        
        return {
            "sentiment": sentiment,
            "strength": strength,
            "related_sectors": related_sectors,
            "related_stocks": related_stocks,
            "duration": duration,
            "catalyst_score": catalyst_score,
            "summary": news_title[:50],
            "reasoning": f"基于规则引擎分析：情绪={sentiment}，强度={strength}",
        }


def get_llm_client(client_type: str = "auto", **kwargs) -> LLMClient:
    """
    获取 LLM 客户端
    
    client_type:
    - "auto": 自动选择（优先 Ollama -> OpenAI -> Anthropic -> 规则引擎）
    - "openai": OpenAI
    - "anthropic": Anthropic Claude
    - "ollama": 本地 Ollama
    - "rule": 规则引擎
    """
    
    if client_type == "openai":
        return OpenAIClient(**kwargs)
    
    elif client_type == "anthropic":
        return AnthropicClient(**kwargs)
    
    elif client_type == "ollama":
        return OllamaClient(**kwargs)
    
    elif client_type == "rule":
        return RuleBasedFallback()
    
    elif client_type == "auto":
        # 优先 Ollama（本地免费）
        try:
            client = OllamaClient()
            # 测试连接
            client.chat([{"role": "user", "content": "test"}], max_tokens=10)
            return client
        except:
            pass
        
        # 尝试 OpenAI
        try:
            return OpenAIClient()
        except:
            pass
        
        # 尝试 Anthropic
        try:
            return AnthropicClient()
        except:
            pass
        
        # 最后回退到规则引擎
        print("⚠ LLM 不可用，使用规则引擎 fallback")
        return RuleBasedFallback()
    
    else:
        raise ValueError(f"未知 LLM 客户端类型: {client_type}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LLM API 适配器")
    parser.add_argument("action", choices=["chat", "analyze", "test"])
    parser.add_argument("--client", default="auto", choices=["auto", "openai", "anthropic", "ollama", "rule"])
    parser.add_argument("--message", help="聊天消息")
    parser.add_argument("--title", help="新闻标题")
    parser.add_argument("--content", help="新闻内容")
    
    args = parser.parse_args()
    
    # 获取客户端
    client = get_llm_client(args.client)
    print(f"使用 LLM 客户端: {client.__class__.__name__}")
    
    if args.action == "chat":
        if not args.message:
            print("错误：需要 --message")
            exit(1)
        
        messages = [{"role": "user", "content": args.message}]
        response = client.chat(messages)
        print(response)
    
    elif args.action == "analyze":
        if not args.title:
            print("错误：需要 --title")
            exit(1)
        
        result = client.analyze_news(args.title, args.content)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    elif args.action == "test":
        print("\n=== 测试聊天 ===")
        messages = [{"role": "user", "content": "你好，请用一句话介绍自己"}]
        response = client.chat(messages, max_tokens=100)
        print(response)
        
        print("\n=== 测试新闻分析 ===")
        result = client.analyze_news(
            "工信部发布AI算力支持政策，多家企业受益",
            "工信部今日发布关于支持AI算力发展的政策文件，将对数据中心、服务器等领域给予补贴..."
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
