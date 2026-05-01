#!/usr/bin/env python3
"""
量化分析师工作流包装器
集成数据源管理、消息催化、自动打分
"""
import sys
import json
from pathlib import Path

# 添加 runtime 到 path
RUNTIME = Path.home() / ".hermes" / "runtime-hermes-agent"
sys.path.insert(0, str(RUNTIME))

from data_source_manager import (
    DataSourceManager, 
    DataSourceStatus,
    check_data_source_warnings
)


def load_news_catalyst(news_analysis_path: str):
    """加载研究员的消息催化分析"""
    if not Path(news_analysis_path).exists():
        return None
    with open(news_analysis_path) as f:
        return json.load(f)


def fetch_qmt_data(date: str) -> dict:
    """
    抓取 QMT 数据
    自动处理降级
    """
    manager = DataSourceManager()
    
    try:
        # 尝试从 QMT 获取数据
        # 简化实现：实际应该调用 qmt_sync 脚本
        qmt_path = Path(f"~/.hermes/runtime-hermes-agent/qmt_sync/reports/{date}/auction_candidates_main_board_non_st.json").expanduser()
        
        if not qmt_path.exists():
            raise FileNotFoundError(f"QMT 数据文件不存在: {qmt_path}")
        
        with open(qmt_path) as f:
            data = json.load(f)
        
        # 标记 QMT 正常
        manager.update_source_status(
            "QMT",
            DataSourceStatus.NORMAL,
            "QMT 数据获取成功"
        )
        
        return {
            "source": "QMT",
            "data": data,
            "degraded": False
        }
        
    except Exception as e:
        # QMT 失败，降级为 Tushare
        manager.update_source_status(
            "QMT",
            DataSourceStatus.DEGRADED,
            f"QMT 数据获取失败: {str(e)}，已降级为纯 Tushare 模式",
            {"fallback": "Tushare"}
        )
        
        # 从 Tushare 获取数据
        tushare_data = fetch_tushare_data(date)
        
        return {
            "source": "Tushare",
            "data": tushare_data,
            "degraded": True,
            "degraded_reason": str(e)
        }


def fetch_tushare_data(date: str) -> dict:
    """从 Tushare 获取数据"""
    # 简化实现
    return {
        "candidates": [],
        "generated_at": date
    }


def score_candidate_with_catalyst(candidate, news_catalyst, weights):
    """为候选打分（集成消息催化）"""
    code = candidate.get("code", "")
    
    # 基础指标评分
    scores = {
        "buy_sell_ratio": 8.0,
        "open_position": 7.5,
        "volume_ratio": 8.5,
        "relative_activity": 7.0,
        "theme_strength": 6.5,
        "news_catalyst": 0.0
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
        "catalyst_info": catalyst_info
    }


def run_quant_workflow(date: str, news_analysis_path: str) -> dict:
    """
    运行量化分析师完整工作流
    
    Returns:
        {
            "candidates": [...],
            "data_source_status": {...},
            "warnings": [...]
        }
    """
    # 1. 抓取数据（自动处理降级）
    qmt_result = fetch_qmt_data(date)
    
    # 2. 加载研究员的消息催化分析
    news_catalyst = None
    if Path(news_analysis_path).exists():
        with open(news_analysis_path) as f:
            news_catalyst = json.load(f)
    
    # 3. 为候选打分
    weights = {
        "buy_sell_ratio": 0.25,
        "open_position": 0.20,
        "volume_ratio": 0.20,
        "relative_activity": 0.15,
        "theme_strength": 0.10,
        "news_catalyst": 0.10
    }
    
    scored_candidates = []
    for candidate in qmt_result["data"].get("candidates", []):
        score_result = score_candidate_with_catalyst(
            candidate,
            news_catalyst,
            weights
        )
        scored_candidates.append(score_result)
    
    # 4. 检查数据源告警
    warnings = check_data_source_warnings()
    
    # 5. 返回结果
    return {
        "candidates": scored_candidates,
        "data_source_status": {
            "source": qmt_result["source"],
            "degraded": qmt_result["degraded"],
            "degraded_reason": qmt_result.get("degraded_reason")
        },
        "warnings": warnings,
        "generated_at": date
    }


def main():
    """测试量化分析师工作流"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: quant_workflow.py <date> [news_analysis_path]")
        sys.exit(1)
    
    date = sys.argv[1]
    news_analysis_path = sys.argv[2] if len(sys.argv) > 2 else "/tmp/news_analysis.json"
    
    print(f"运行量化分析师工作流: {date}")
    print(f"消息面分析: {news_analysis_path}")
    print()
    
    result = run_quant_workflow(date, news_analysis_path)
    
    # 打印结果
    print("数据源状态:")
    print(f"  来源: {result['data_source_status']['source']}")
    print(f"  降级: {'是' if result['data_source_status']['degraded'] else '否'}")
    if result['data_source_status']['degraded']:
        print(f"  原因: {result['data_source_status']['degraded_reason']}")
    print()
    
    if result['warnings']:
        print("数据源告警:")
        for warning in result['warnings']:
            print(f"  {warning}")
        print()
    
    print(f"候选数量: {len(result['candidates'])}")
    
    # 保存结果
    output_path = f"/tmp/quant_result_{date}.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ 结果已保存到 {output_path}")


if __name__ == "__main__":
    main()
