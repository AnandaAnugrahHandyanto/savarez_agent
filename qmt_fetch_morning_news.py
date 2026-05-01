#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
早盘消息抓取
从东方财富、财联社等抓取最新财经新闻
"""

import json
import requests
from pathlib import Path
from datetime import datetime, date
from typing import Optional

HERMES_HOME = Path.home() / ".hermes"
NEWS_DIR = HERMES_HOME / "state" / "qmt_news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)


def fetch_eastmoney_news(limit: int = 20) -> list[dict]:
    """抓取东方财富快讯"""
    url = "https://np-anotice-stock.eastmoney.com/api/content/ann"
    params = {
        "page_size": limit,
        "page_index": 1,
        "type": "0",  # 0=快讯
        "client_source": "web",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        news_list = []
        for item in data.get("data", {}).get("list", []):
            news_list.append({
                "source": "东方财富",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "url": item.get("url", ""),
                "publish_time": item.get("notice_date", ""),
            })
        
        return news_list
    
    except Exception as e:
        print(f"抓取东方财富失败: {e}")
        return []


def fetch_cls_news(limit: int = 20) -> list[dict]:
    """抓取财联社快讯"""
    url = "https://www.cls.cn/api/sw"
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
        "rever": "1",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        news_list = []
        for item in data.get("data", {}).get("roll_data", [])[:limit]:
            news_list.append({
                "source": "财联社",
                "title": item.get("title", ""),
                "content": item.get("content", ""),
                "url": f"https://www.cls.cn/detail/{item.get('id', '')}",
                "publish_time": item.get("ctime", ""),
            })
        
        return news_list
    
    except Exception as e:
        print(f"抓取财联社失败: {e}")
        return []


def fetch_sina_finance_news(limit: int = 20) -> list[dict]:
    """抓取新浪财经要闻"""
    url = "https://feed.mix.sina.com.cn/api/roll/get"
    params = {
        "pageid": "153",
        "lid": "2509",
        "num": limit,
        "versionNumber": "1.2.8",
        "page": "1",
    }
    
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        news_list = []
        for item in data.get("result", {}).get("data", []):
            news_list.append({
                "source": "新浪财经",
                "title": item.get("title", ""),
                "content": item.get("intro", ""),
                "url": item.get("url", ""),
                "publish_time": item.get("ctime", ""),
            })
        
        return news_list
    
    except Exception as e:
        print(f"抓取新浪财经失败: {e}")
        return []


def fetch_all_morning_news() -> list[dict]:
    """抓取所有早盘新闻"""
    all_news = []
    
    print("抓取东方财富...")
    all_news.extend(fetch_eastmoney_news(20))
    
    print("抓取财联社...")
    all_news.extend(fetch_cls_news(20))
    
    print("抓取新浪财经...")
    all_news.extend(fetch_sina_finance_news(20))
    
    # 去重
    seen_titles = set()
    unique_news = []
    for news in all_news:
        title = news["title"]
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(news)
    
    return unique_news


def save_morning_news(news_list: list[dict]):
    """保存早盘新闻"""
    today = date.today().isoformat()
    output_file = NEWS_DIR / f"morning_news_{today}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "date": today,
            "fetched_at": datetime.now().isoformat(),
            "count": len(news_list),
            "news": news_list,
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 保存 {len(news_list)} 条新闻: {output_file}")
    return output_file


if __name__ == "__main__":
    print("=== 抓取早盘新闻 ===")
    news_list = fetch_all_morning_news()
    
    if news_list:
        output_file = save_morning_news(news_list)
        print(f"\n共抓取 {len(news_list)} 条新闻")
        print(f"保存路径: {output_file}")
    else:
        print("未抓取到新闻")
