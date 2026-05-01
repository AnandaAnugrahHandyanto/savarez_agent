#!/usr/bin/env python3
"""
量化分析师真实数据工作流
接入真实的 Tushare、QMT、问财网数据
"""
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path.home() / ".hermes"
RUNTIME = HERMES_HOME / "runtime-hermes-agent"
sys.path.insert(0, str(RUNTIME))

from data_source_manager import DataSourceManager, DataSourceStatus, check_data_source_warnings


def fetch_tushare_auction_data(trade_date: str) -> dict:
    """
    调用真实的 tushare_auction_0927_fetch.py
    """
    manager = DataSourceManager()
    
    try:
        # 运行 tushare 脚本
        script_path = HERMES_HOME / "scripts" / "tushare_auction_0927_fetch.py"
        
        result = subprocess.run(
            ["python3", str(script_path), "--date", trade_date],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(RUNTIME)
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Tushare 脚本执行失败: {result.stderr}")
        
        # 读取生成的文件
        report_dir = RUNTIME / "qmt_sync" / "reports" / trade_date
        auction_file = report_dir / "tushare_auction_0927.json"
        
        if not auction_file.exists():
            raise FileNotFoundError(f"Tushare 数据文件不存在: {auction_file}")
        
        with open(auction_file) as f:
            data = json.load(f)
        
        # 标记 Tushare 正常
        manager.update_source_status(
            "Tushare",
            DataSourceStatus.NORMAL,
            "Tushare 数据获取成功"
        )
        
        return {
            "source": "Tushare",
            "data": data,
            "degraded": False
        }
        
    except Exception as e:
        # Tushare 失败
        manager.update_source_status(
            "Tushare",
            DataSourceStatus.FAILED,
            f"Tushare 数据获取失败: {str(e)}"
        )
        
        return {
            "source": "Tushare",
            "data": {"candidates": []},
            "degraded": True,
            "degraded_reason": str(e)
        }


def fetch_qmt_data(trade_date: str) -> dict:
    """
    从 QMT 获取数据
    """
    manager = DataSourceManager()
    
    try:
        # QMT 数据路径
        qmt_file = RUNTIME / "qmt_sync" / "reports" / trade_date / "auction_candidates_main_board_non_st.json"
        
        if not qmt_file.exists():
            raise FileNotFoundError(f"QMT 数据文件不存在: {qmt_file}")
        
        with open(qmt_file) as f:
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
            f"QMT 数据获取失败: {str(e)}，已降级为纯 Tushare 模式"
        )
        
        # 尝试从 Tushare 获取
        return fetch_tushare_auction_data(trade_date)


def run_qmt_candidate_ranker(input_file: str, news_analysis_path: str = None) -> dict:
    """
    调用真实的 qmt_candidate_ranker.py
    """
    try:
        # 构建命令
        cmd = ["python3", str(RUNTIME / "qmt_candidate_ranker.py"), input_file]
        
        # 运行打分脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(RUNTIME)
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"打分脚本执行失败: {result.stderr}")
        
        # 解析输出
        output = json.loads(result.stdout)
        
        # 如果有消息面分析，补充消息催化评分
        if news_analysis_path and Path(news_analysis_path).exists():
            with open(news_analysis_path) as f:
                news_catalyst = json.load(f)
            
            # 为每个候选补充消息催化评分
            for candidate in output.get("candidates", []):
                code = candidate.get("code")
                if code and "catalyst_by_stock" in news_catalyst:
                    stock_catalyst = news_catalyst["catalyst_by_stock"].get(code)
                    if stock_catalyst:
                        candidate["news_catalyst_score"] = stock_catalyst["score"]
                        candidate["news_catalyst_info"] = stock_catalyst
        
        return output
        
    except Exception as e:
        raise RuntimeError(f"候选打分失败: {str(e)}")


def run_real_quant_workflow(trade_date: str, news_analysis_path: str = None) -> dict:
    """
    运行真实数据的量化分析师工作流
    
    Returns:
        {
            "candidates": [...],
            "data_source_status": {...},
            "warnings": [...],
            "generated_at": str
        }
    """
    # 1. 尝试从 QMT 获取数据（失败则降级为 Tushare）
    qmt_result = fetch_qmt_data(trade_date)
    
    # 2. 如果 QMT 降级了，从 Tushare 获取
    if qmt_result["degraded"]:
        print(f"⚠️ QMT 降级: {qmt_result['degraded_reason']}")
        tushare_result = fetch_tushare_auction_data(trade_date)
        data_source = tushare_result
    else:
        data_source = qmt_result
    
    # 3. 保存临时数据文件
    temp_file = Path(f"/tmp/auction_data_{trade_date}.json")
    with open(temp_file, "w") as f:
        json.dump(data_source["data"], f, ensure_ascii=False, indent=2)
    
    # 4. 运行打分脚本
    scored_result = run_qmt_candidate_ranker(str(temp_file), news_analysis_path)
    
    # 5. 检查数据源告警
    warnings = check_data_source_warnings()
    
    # 6. 返回结果
    return {
        "candidates": scored_result.get("candidates", []),
        "data_source_status": {
            "source": data_source["source"],
            "degraded": data_source["degraded"],
            "degraded_reason": data_source.get("degraded_reason")
        },
        "warnings": warnings,
        "scoring_summary": scored_result.get("summary", {}),
        "generated_at": datetime.now().isoformat()
    }


def main():
    """测试真实数据工作流"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: quant_real_workflow.py <trade_date> [news_analysis_path]")
        print("示例: quant_real_workflow.py 20260421 /tmp/news_analysis.json")
        sys.exit(1)
    
    trade_date = sys.argv[1]
    news_analysis_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"运行真实数据量化工作流: {trade_date}")
    if news_analysis_path:
        print(f"消息面分析: {news_analysis_path}")
    print()
    
    try:
        result = run_real_quant_workflow(trade_date, news_analysis_path)
        
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
        
        if result['candidates']:
            print("\nTop 3 候选:")
            for i, candidate in enumerate(result['candidates'][:3], 1):
                print(f"  {i}. {candidate.get('code')} {candidate.get('name')}")
                print(f"     总分: {candidate.get('total_score', 0):.2f}")
                if 'news_catalyst_score' in candidate:
                    print(f"     消息催化: {candidate['news_catalyst_score']:.1f}/10")
        
        # 保存结果
        output_path = f"/tmp/quant_real_result_{trade_date}.json"
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ 结果已保存到 {output_path}")
        
    except Exception as e:
        print(f"\n✗ 执行失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
