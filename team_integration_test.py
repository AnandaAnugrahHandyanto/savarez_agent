#!/usr/bin/env python3
"""
Hermes Team 集成测试
端到端测试完整工作流
"""
import json
import sys
from pathlib import Path
from datetime import datetime

HERMES_HOME = Path.home() / ".hermes"
RUNTIME = HERMES_HOME / "runtime-hermes-agent"

sys.path.insert(0, str(RUNTIME))

from team_auto_approval import AutoApprovalEngine
from team_dedupe_engine import DedupeEngine, check_report_change
from data_source_manager import DataSourceManager, DataSourceStatus, check_data_source_warnings
from researcher_news_catalyst import analyze_news_catalyst, save_news_analysis
from quant_workflow import run_quant_workflow


class TeamIntegrationTest:
    """团队集成测试"""
    
    def __init__(self):
        self.test_date = datetime.now().strftime("%Y%m%d")
        self.test_dir = Path("/tmp/team_integration_test")
        self.test_dir.mkdir(exist_ok=True)
        self.results = []
    
    def log(self, message: str, status: str = "info"):
        """记录日志"""
        icons = {
            "info": "ℹ️",
            "success": "✓",
            "error": "✗",
            "warning": "⚠️"
        }
        icon = icons.get(status, "")
        print(f"{icon} {message}")
        self.results.append({"message": message, "status": status})
    
    def test_researcher_workflow(self) -> bool:
        """测试研究员工作流"""
        self.log("测试研究员工作流...", "info")
        
        try:
            # 模拟新闻数据
            news_items = [
                {"title": "AI芯片订单大增", "source": "财联社", "time": "09:00"},
                {"title": "新能源政策利好", "source": "东方财富", "time": "08:30"}
            ]
            
            # 分析消息面
            analysis = analyze_news_catalyst(news_items)
            
            # 保存结果
            output_path = self.test_dir / "news_analysis.json"
            save_news_analysis(str(output_path), analysis)
            
            # 验证
            assert output_path.exists(), "消息面分析文件未生成"
            assert analysis["overall_catalyst_score"] > 0, "催化评分异常"
            assert "catalyst_by_stock" in analysis, "缺少个股催化数据"
            
            self.log("研究员工作流测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"研究员工作流测试失败: {e}", "error")
            return False
    
    def test_quant_workflow(self) -> bool:
        """测试量化分析师工作流"""
        self.log("测试量化分析师工作流...", "info")
        
        try:
            news_analysis_path = str(self.test_dir / "news_analysis.json")
            
            # 运行量化工作流
            result = run_quant_workflow(self.test_date, news_analysis_path)
            
            # 验证
            assert "data_source_status" in result, "缺少数据源状态"
            assert "warnings" in result, "缺少告警信息"
            assert "candidates" in result, "缺少候选数据"
            
            # 检查数据源降级标记
            if result["data_source_status"]["degraded"]:
                self.log(f"数据源已降级: {result['data_source_status']['source']}", "warning")
            
            self.log("量化分析师工作流测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"量化分析师工作流测试失败: {e}", "error")
            return False
    
    def test_auto_approval(self) -> bool:
        """测试自动审批"""
        self.log("测试自动审批引擎...", "info")
        
        try:
            engine = AutoApprovalEngine()
            
            # 测试场景 1: 强势日，应该自动通过
            context1 = {
                "market_env": "强势日",
                "candidate_count": 5,
                "strong_catalyst_count": 3
            }
            result1 = engine.approve_report("morning_report", "/tmp/test.md", context1)
            assert result1["approved"], "强势日应该自动通过"
            assert result1["auto"], "应该是自动审批"
            
            # 测试场景 2: 退潮日，应该需要人工审批
            context2 = {
                "market_env": "退潮日",
                "candidate_count": 1,
                "strong_catalyst_count": 0
            }
            result2 = engine.approve_report("morning_report", "/tmp/test.md", context2)
            assert not result2["approved"], "退潮日应该需要人工审批"
            
            self.log("自动审批引擎测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"自动审批引擎测试失败: {e}", "error")
            return False
    
    def test_dedupe_engine(self) -> bool:
        """测试去重引擎"""
        self.log("测试去重引擎...", "info")
        
        try:
            # 创建测试报告
            report_path = self.test_dir / "test_report.md"
            report_path.write_text("# 测试报告\n\n生成时间: 2026-04-21 09:00\n\n内容: 测试")
            
            # 首次检查（应该是 CHANGED）
            result1 = check_report_change("test_report", str(report_path), commit=False)
            assert result1["status"] == "CHANGED", "首次应该是 CHANGED"
            
            # 提交基线
            result2 = check_report_change("test_report", str(report_path), commit=True)
            assert result2["state_committed"], "应该提交基线"
            
            # 再次检查（应该是 UNCHANGED）
            result3 = check_report_change("test_report", str(report_path), commit=False)
            assert result3["status"] == "UNCHANGED", "再次检查应该是 UNCHANGED"
            
            # 修改内容
            report_path.write_text("# 测试报告\n\n生成时间: 2026-04-21 09:05\n\n内容: 测试修改")
            
            # 检查（应该是 CHANGED）
            result4 = check_report_change("test_report", str(report_path), commit=False)
            assert result4["status"] == "CHANGED", "内容变化应该是 CHANGED"
            
            self.log("去重引擎测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"去重引擎测试失败: {e}", "error")
            return False
    
    def test_data_source_manager(self) -> bool:
        """测试数据源管理器"""
        self.log("测试数据源管理器...", "info")
        
        try:
            manager = DataSourceManager()
            
            # 标记 QMT 降级
            manager.update_source_status(
                "QMT_TEST",
                DataSourceStatus.DEGRADED,
                "测试降级"
            )
            
            # 检查状态
            status = manager.get_source_status("QMT_TEST")
            assert status is not None, "应该能获取状态"
            assert status["current_status"] == "degraded", "状态应该是 degraded"
            
            # 检查告警
            warnings = check_data_source_warnings()
            assert any("QMT_TEST" in w for w in warnings), "应该有告警"
            
            self.log("数据源管理器测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"数据源管理器测试失败: {e}", "error")
            return False
    
    def test_end_to_end(self) -> bool:
        """端到端测试"""
        self.log("端到端测试...", "info")
        
        try:
            # 1. 研究员分析消息面
            news_items = [{"title": "测试新闻", "source": "测试", "time": "09:00"}]
            analysis = analyze_news_catalyst(news_items)
            news_path = self.test_dir / "e2e_news.json"
            save_news_analysis(str(news_path), analysis)
            
            # 2. 量化分析师打分
            quant_result = run_quant_workflow(self.test_date, str(news_path))
            
            # 3. 执行官生成报告
            report_path = self.test_dir / "e2e_report.md"
            report_content = f"""# 早盘推送 {self.test_date}

## 消息面分析
整体催化评分: {analysis['overall_catalyst_score']}/10

## 候选池
候选数量: {len(quant_result['candidates'])}

## 数据源状态
来源: {quant_result['data_source_status']['source']}
降级: {'是' if quant_result['data_source_status']['degraded'] else '否'}
"""
            report_path.write_text(report_content)
            
            # 4. CIO 自动审批
            engine = AutoApprovalEngine()
            context = {
                "market_env": "强势日",
                "candidate_count": len(quant_result['candidates']),
                "strong_catalyst_count": 2
            }
            approval = engine.approve_report("morning_report", str(report_path), context)
            
            # 5. 执行官去重检查
            dedupe_result = check_report_change("e2e_report", str(report_path), commit=False)
            
            # 验证
            assert analysis["overall_catalyst_score"] > 0, "消息面分析失败"
            assert "candidates" in quant_result, "量化分析失败"
            assert report_path.exists(), "报告生成失败"
            assert "approved" in approval, "审批失败"
            assert dedupe_result["status"] in ["CHANGED", "UNCHANGED"], "去重检查失败"
            
            self.log("端到端测试通过", "success")
            return True
            
        except Exception as e:
            self.log(f"端到端测试失败: {e}", "error")
            return False
    
    def run_all_tests(self):
        """运行所有测试"""
        print("="*60)
        print("Hermes Team 集成测试")
        print("="*60)
        print()
        
        tests = [
            ("研究员工作流", self.test_researcher_workflow),
            ("量化分析师工作流", self.test_quant_workflow),
            ("自动审批引擎", self.test_auto_approval),
            ("去重引擎", self.test_dedupe_engine),
            ("数据源管理器", self.test_data_source_manager),
            ("端到端流程", self.test_end_to_end)
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            print(f"\n{'='*60}")
            print(f"测试: {test_name}")
            print(f"{'='*60}")
            
            if test_func():
                passed += 1
            else:
                failed += 1
        
        # 总结
        print(f"\n{'='*60}")
        print("测试总结")
        print(f"{'='*60}")
        print(f"\n总计: {len(tests)} 个测试")
        print(f"通过: {passed}")
        print(f"失败: {failed}")
        
        if failed == 0:
            print("\n✓ 所有测试通过")
            return 0
        else:
            print(f"\n✗ {failed} 个测试失败")
            return 1


def main():
    test = TeamIntegrationTest()
    exit_code = test.run_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
