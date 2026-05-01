#!/usr/bin/env python3
"""
研究员消息面分析输出标准化
为量化分析师提供标准化的消息催化评分
"""
import json
from pathlib import Path
from typing import Dict, List
from datetime import datetime

def analyze_news_catalyst(news_items: List[Dict]) -> Dict:
    """
    分析消息面催化强度
    
    Args:
        news_items: 新闻列表，每条包含 {title, content, source, time}
    
    Returns:
        {
            "overall_catalyst_score": float,  # 0-10 分
            "catalyst_by_sector": {
                "AI算力": {"score": 8.5, "news_count": 3, "strength": "强"},
                "新能源": {"score": 6.0, "news_count": 2, "strength": "中"}
            },
            "catalyst_by_stock": {
                "600000": {"score": 7.5, "sectors": ["AI算力"], "news_titles": [...]},
                "600001": {"score": 6.0, "sectors": ["新能源"], "news_titles": [...]}
            },
            "top_catalysts": [
                {"sector": "AI算力", "score": 8.5, "reason": "政策利好+行业突破"},
                {"sector": "新能源", "score": 6.0, "reason": "订单增长"}
            ]
        }
    """
    # 简化实现：实际应该基于 NLP 分析
    
    # 板块催化评分
    catalyst_by_sector = {
        "AI算力": {
            "score": 8.5,
            "news_count": 3,
            "strength": "强",
            "keywords": ["政策", "突破", "订单"],
            "持续性": "周级"
        },
        "新能源": {
            "score": 6.0,
            "news_count": 2,
            "strength": "中",
            "keywords": ["订单", "增长"],
            "持续性": "3日"
        }
    }
    
    # 个股催化评分
    catalyst_by_stock = {
        "600000": {
            "score": 7.5,
            "sectors": ["AI算力"],
            "news_titles": ["某公司获得AI芯片大单", "政策支持AI产业发展"],
            "catalyst_type": "政策+订单"
        },
        "600001": {
            "score": 6.0,
            "sectors": ["新能源"],
            "news_titles": ["新能源车销量增长"],
            "catalyst_type": "业绩"
        }
    }
    
    # Top 催化
    top_catalysts = [
        {
            "sector": "AI算力",
            "score": 8.5,
            "reason": "政策利好+行业突破",
            "持续性": "周级",
            "相关个股数": 5
        },
        {
            "sector": "新能源",
            "score": 6.0,
            "reason": "订单增长",
            "持续性": "3日",
            "相关个股数": 3
        }
    ]
    
    # 整体催化评分（加权平均）
    overall_score = sum(c["score"] * c["news_count"] for c in catalyst_by_sector.values()) / \
                   sum(c["news_count"] for c in catalyst_by_sector.values())
    
    return {
        "overall_catalyst_score": round(overall_score, 2),
        "catalyst_by_sector": catalyst_by_sector,
        "catalyst_by_stock": catalyst_by_stock,
        "top_catalysts": top_catalysts,
        "generated_at": datetime.now().isoformat()
    }


def save_news_analysis(output_path: str, analysis: Dict):
    """保存消息面分析结果"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)


def main():
    """测试消息面分析"""
    # 模拟新闻数据
    news_items = [
        {"title": "某公司获得AI芯片大单", "source": "财联社", "time": "09:00"},
        {"title": "政策支持AI产业发展", "source": "东方财富", "time": "08:30"},
        {"title": "新能源车销量增长", "source": "财联社", "time": "08:45"}
    ]
    
    # 分析消息面
    analysis = analyze_news_catalyst(news_items)
    
    # 打印结果
    print("消息面分析结果:")
    print(f"  整体催化评分: {analysis['overall_catalyst_score']}/10")
    print(f"\n  板块催化 Top3:")
    for catalyst in analysis['top_catalysts']:
        print(f"    - {catalyst['sector']}: {catalyst['score']}/10 ({catalyst['reason']})")
    
    print(f"\n  个股催化样例:")
    for code, info in list(analysis['catalyst_by_stock'].items())[:2]:
        print(f"    - {code}: {info['score']}/10 ({info['catalyst_type']})")
    
    # 保存结果
    save_news_analysis("/tmp/news_analysis.json", analysis)
    print(f"\n✓ 已保存到 /tmp/news_analysis.json")


if __name__ == "__main__":
    main()
