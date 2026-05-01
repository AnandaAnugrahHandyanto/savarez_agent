#!/usr/bin/env python3
"""
数据集成测试
使用真实历史数据测试完整工作流
"""
import sys
import json
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path.home() / ".hermes"
RUNTIME = HERMES_HOME / "runtime-hermes-agent"
sys.path.insert(0, str(RUNTIME))

from quant_real_workflow import run_real_quant_workflow


def find_latest_trade_date() -> str:
    """查找最近的交易日数据"""
    reports_dir = RUNTIME / "qmt_sync" / "reports"
    
    if not reports_dir.exists():
        return None
    
    # 查找最近的有数据的日期
    dates = sorted([d.name for d in reports_dir.iterdir() if d.is_dir()], reverse=True)
    
    for date in dates:
        date_dir = reports_dir / date
        # 检查是否有候选数据文件
        if (date_dir / "auction_candidates_main_board_non_st.json").exists():
            return date
    
    return None


def test_with_real_data():
    """使用真实数据测试"""
    print("="*60)
    print("数据集成测试")
    print("="*60)
    print()
    
    # 1. 查找最近的交易日
    print("查找最近的交易日数据...")
    trade_date = find_latest_trade_date()
    
    if not trade_date:
        print("✗ 未找到历史数据")
        print("\n提示: 请先运行一次真实的数据抓取脚本")
        return False
    
    print(f"✓ 找到交易日: {trade_date}\n")
    
    # 2. 运行真实数据工作流
    print("运行真实数据工作流...")
    try:
        result = run_real_quant_workflow(trade_date)
        
        # 3. 验证结果
        print("\n验证结果:")
        
        # 检查数据源状态
        assert "data_source_status" in result, "缺少数据源状态"
        print(f"  ✓ 数据源: {result['data_source_status']['source']}")
        
        # 检查候选数据
        assert "candidates" in result, "缺少候选数据"
        candidate_count = len(result['candidates'])
        print(f"  ✓ 候选数量: {candidate_count}")
        
        # 检查告警
        assert "warnings" in result, "缺少告警信息"
        if result['warnings']:
            print(f"  ⚠️ 告警数量: {len(result['warnings'])}")
        else:
            print(f"  ✓ 无告警")
        
        # 检查候选字段完整性
        if candidate_count > 0:
            first_candidate = result['candidates'][0]
            required_fields = ['code', 'name', 'total_score']
            
            for field in required_fields:
                assert field in first_candidate, f"候选缺少字段: {field}"
            
            print(f"  ✓ 候选字段完整")
            
            # 显示 Top 3
            print("\n  Top 3 候选:")
            for i, candidate in enumerate(result['candidates'][:3], 1):
                print(f"    {i}. {candidate['code']} {candidate['name']}")
                print(f"       总分: {candidate.get('total_score', 0):.2f}")
        
        print("\n✓ 数据集成测试通过")
        return True
        
    except Exception as e:
        print(f"\n✗ 数据集成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    success = test_with_real_data()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
