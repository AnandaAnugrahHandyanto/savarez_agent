#!/usr/bin/env python3
"""
量化分析师候选打分（集成研究员消息催化）
"""
import json
from pathlib import Path
from typing import Dict, Optional

def load_news_catalyst(news_analysis_path: str) -> Optional[Dict]:
    """加载研究员的消息催化分析"""
    analysis_file = Path(news_analysis_path)
    if not analysis_file.exists():
        return None
    
    with open(analysis_file, encoding="utf-8") as f:
        return json.load(f)


def score_candidate_with_catalyst(
    candidate: Dict,
    news_catalyst: Optional[Dict],
    weights: Dict
) -> Dict:
    """
    为候选打分（集成消息催化）
    
    Args:
        candidate: 候选数据 {code, name, pct, amount, volume, ...}
        news_catalyst: 研究员的消息催化分析
        weights: 权重配置
    
    Returns:
        {
            "code": str,
            "total_score": float,
            "scores": {
                "buy_sell_ratio": float,
                "open_position": float,
                "volume_ratio": float,
                "relative_activity": float,
                "theme_strength": float,
                "news_catalyst": float  # 直接从研究员读取
            },
            "catalyst_info": {
                "score": float,
                "sectors": list,
                "catalyst_type": str
            }
        }
    """
    code = candidate["code"]
    
    # 基础指标评分（简化实现）
    scores = {
        "buy_sell_ratio": 8.0,
        "open_position": 7.5,
        "volume_ratio": 8.5,
        "relative_activity": 7.0,
        "theme_strength": 6.5,
        "news_catalyst": 0.0  # 默认 0
    }
    
    # 从研究员的分析中读取消息催化评分
    catalyst_info = None
    if news_catalyst and "catalyst_by_stock" in news_catalyst:
        stock_catalyst = news_catalyst["catalyst_by_stock"].get(code)
        if stock_catalyst:
            scores["news_catalyst"] = stock_catalyst["score"]
            catalyst_info = stock_catalyst
    
    # 计算总分
    total_score = sum(scores[k] * weights[k] for k in scores.keys())
    
    return {
        "code": code,
        "name": candidate.get("name", ""),
        "total_score": round(total_score, 2),
        "scores": scores,
        "catalyst_info": catalyst_info,
        "weights": weights
    }


def main():
    """测试集成消息催化的打分"""
    # 加载研究员的消息催化分析
    news_catalyst = load_news_catalyst("/tmp/news_analysis.json")
    
    # 权重配置
    weights = {
        "buy_sell_ratio": 0.25,
        "open_position": 0.20,
        "volume_ratio": 0.20,
        "relative_activity": 0.15,
        "theme_strength": 0.10,
        "news_catalyst": 0.10  # 消息催化权重 10%
    }
    
    # 模拟候选数据
    candidates = [
        {"code": "600000", "name": "某AI公司", "pct": 9.95},
        {"code": "600001", "name": "某新能源公司", "pct": 9.90},
        {"code": "600002", "name": "某其他公司", "pct": 9.85}
    ]
    
    print("候选打分结果（集成消息催化）:\n")
    for candidate in candidates:
        result = score_candidate_with_catalyst(candidate, news_catalyst, weights)
        
        print(f"{result['code']} {result['name']}")
        print(f"  总分: {result['total_score']}/10")
        print(f"  消息催化: {result['scores']['news_catalyst']}/10", end="")
        
        if result['catalyst_info']:
            print(f" ({result['catalyst_info']['catalyst_type']})")
            print(f"    相关板块: {', '.join(result['catalyst_info']['sectors'])}")
        else:
            print(" (无消息催化)")
        print()


if __name__ == "__main__":
    main()
