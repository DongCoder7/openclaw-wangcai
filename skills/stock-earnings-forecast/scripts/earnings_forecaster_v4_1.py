#!/root/.openclaw/workspace/venv/bin/python3
"""
个股盈利预测工具 v4.1 - 经营杠杆+动态PE版
基于行业标杆经营杠杆效应和动态PE变化的盈利预测
"""

import json
import os
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 添加长桥API路径
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

@dataclass
class QuarterData:
    """季度数据"""
    year: int
    quarter: int
    revenue: float      # 营收（亿元）
    profit: float       # 净利润（亿元）
    pe: float          # 季度末PE
    
    @property
    def margin(self) -> float:
        return self.profit / self.revenue if self.revenue > 0 else 0
    
    @property
    def period(self) -> str:
        return f"{self.year}Q{self.quarter}"


@dataclass
class BenchmarkStock:
    """标杆企业数据"""
    name: str
    code: str
    weight: float
    quarters: List[QuarterData] = None  # 最近4个季度数据
    
    def __post_init__(self):
        if self.quarters is None:
            self.quarters = []
    
    @property
    def latest_pe(self) -> float:
        """最新PE"""
        if self.quarters:
            return self.quarters[-1].pe
        return 0
    
    @property
    def revenue_qoq(self) -> float:
        """营收环比增速（最近季度）"""
        if len(self.quarters) >= 2:
            q1, q0 = self.quarters[-1], self.quarters[-2]
            return (q1.revenue - q0.revenue) / q0.revenue
        return 0
    
    @property
    def profit_qoq(self) -> float:
        """净利润环比增速（最近季度）"""
        if len(self.quarters) >= 2:
            q1, q0 = self.quarters[-1], self.quarters[-2]
            return (q1.profit - q0.profit) / q0.profit if q0.profit != 0 else 0
        return 0
    
    @property
    def operating_leverage(self) -> float:
        """经营杠杆系数 = 利润增速/营收增速"""
        rev_growth = self.revenue_qoq
        profit_growth = self.profit_qoq
        if abs(rev_growth) > 0.001:  # 避免除0
            return profit_growth / rev_growth
        return 1.0


class OperatingLeverageForecaster:
    """
    经营杠杆预测器
    
    核心逻辑：
    1. 获取标杆企业季度数据（营收、利润、PE）
    2. 计算环比增速和经营杠杆系数
    3. 应用到目标企业：
       - 营收增长 = 标杆平均营收增速 × (1 + 市占率变化)
       - 利润增长 = 营收增长 × 经营杠杆系数
       - 固定成本不变，变动成本随营收线性变化
    4. 动态PE估值（基于行业PE趋势）
    """
    
    def __init__(self):
        self.benchmarks: List[BenchmarkStock] = []
        self.target_code = ""
        self.target_name = ""
        self.target_base = {}
        
    def add_benchmark(self, name: str, code: str, weight: float):
        """添加标杆企业"""
        self.benchmarks.append(BenchmarkStock(name=name, code=code, weight=weight))
    
    def fetch_benchmark_data(self, code: str) -> List[QuarterData]:
        """
        获取标杆企业季度数据（使用长桥API）
        
        实际实现应该调用长桥API获取：
        - 最近4个季度营收
        - 最近4个季度净利润
        - 季度末PE
        """
        # TODO: 实际实现需要调用长桥API
        # 这里先用模拟数据演示逻辑
        
        # 模拟天孚通信近4季度数据
        if "300394" in code:  # 天孚通信
            return [
                QuarterData(2024, 1, 6.5, 2.1, 42),
                QuarterData(2024, 2, 7.2, 2.5, 45),
                QuarterData(2024, 3, 8.1, 2.9, 48),
                QuarterData(2024, 4, 9.0, 3.3, 45),  # 最新
            ]
        elif "300308" in code:  # 中际旭创
            return [
                QuarterData(2024, 1, 45, 8.5, 32),
                QuarterData(2024, 2, 52, 10.2, 35),
                QuarterData(2024, 3, 58, 11.8, 38),
                QuarterData(2024, 4, 65, 13.5, 35),  # 最新
            ]
        elif "300502" in code:  # 新易盛
            return [
                QuarterData(2024, 1, 12, 2.8, 38),
                QuarterData(2024, 2, 14, 3.5, 42),
                QuarterData(2024, 3, 16, 4.2, 45),
                QuarterData(2024, 4, 18, 4.8, 40),  # 最新
            ]
        return []
    
    def load_all_benchmark_data(self):
        """加载所有标杆企业数据"""
        for b in self.benchmarks:
            b.quarters = self.fetch_benchmark_data(b.code)
            print(f"  {b.name}: 最新PE={b.latest_pe}, 营收环比={b.revenue_qoq:+.1%}, 经营杠杆={b.operating_leverage:.2f}")
    
    def set_target(self, code: str, name: str, 
                   revenue_2024: float, profit_2024: float,
                   total_shares: float):
        """设置目标企业"""
        self.target_code = code
        self.target_name = name
        self.target_base = {
            "revenue_2024": revenue_2024,
            "profit_2024": profit_2024,
            "margin_2024": profit_2024 / revenue_2024 if revenue_2024 > 0 else 0,
            "total_shares": total_shares
        }
    
    def get_industry_parameters(self) -> Dict:
        """获取行业综合参数"""
        if not self.benchmarks:
            return {}
        
        total_weight = sum(b.weight for b in self.benchmarks)
        
        # 加权平均PE（最新）
        avg_pe = sum(b.latest_pe * b.weight for b in self.benchmarks) / total_weight
        
        # 加权平均营收环比增速
        avg_revenue_qoq = sum(b.revenue_qoq * b.weight for b in self.benchmarks) / total_weight
        
        # 加权平均利润环比增速
        avg_profit_qoq = sum(b.profit_qoq * b.weight for b in self.benchmarks) / total_weight
        
        # 加权平均经营杠杆系数
        avg_leverage = sum(b.operating_leverage * b.weight for b in self.benchmarks) / total_weight
        
        # 加权平均净利润率
        avg_margin = sum(b.quarters[-1].margin * b.weight for b in self.benchmarks if b.quarters) / total_weight
        
        return {
            "avg_pe": avg_pe,
            "avg_revenue_qoq": avg_revenue_qoq,  # 季度环比
            "avg_profit_qoq": avg_profit_qoq,
            "avg_operating_leverage": avg_leverage,
            "avg_profit_margin": avg_margin,
            "benchmark_count": len(self.benchmarks)
        }
    
    def forecast_2025_2026(self, market_share_change: float = 0) -> Dict:
        """
        预测2025和2026年业绩
        
        经营杠杆模型：
        - 营收增长 = 标杆季度环比增速年化 × (1 + 市占率变化)
        - 利润增长 = 营收增长 × 经营杠杆系数
        - 固定成本假设：年度固定成本不变，只变动变动成本
        """
        params = self.get_industry_parameters()
        
        base_rev = self.target_base["revenue_2024"]
        base_profit = self.target_base["profit_2024"]
        base_margin = self.target_base["margin_2024"]
        
        # 季度环比年化（假设每个季度增速相同）
        qoq = params["avg_revenue_qoq"]
        annual_growth = (1 + qoq) ** 4 - 1  # 年化增速
        
        # 2025年预测
        rev_growth_2025 = annual_growth * (1 + market_share_change)
        revenue_2025 = base_rev * (1 + rev_growth_2025)
        
        # 利润增长 = 营收增长 × 经营杠杆
        leverage = params["avg_operating_leverage"]
        profit_growth_2025 = rev_growth_2025 * leverage
        profit_2025 = base_profit * (1 + profit_growth_2025)
        
        # 净利润率（基于经营杠杆）
        margin_2025 = profit_2025 / revenue_2025 if revenue_2025 > 0 else base_margin
        
        # 2026年预测（增速放缓20%）
        rev_growth_2026 = rev_growth_2025 * 0.8
        revenue_2026 = revenue_2025 * (1 + rev_growth_2026)
        
        profit_growth_2026 = rev_growth_2026 * leverage * 0.9  # 杠杆效应递减
        profit_2026 = profit_2025 * (1 + profit_growth_2026)
        margin_2026 = profit_2026 / revenue_2026 if revenue_2026 > 0 else margin_2025
        
        # 动态PE估值（使用最新行业平均PE）
        target_pe = params["avg_pe"]
        
        # 目标市值
        cap_2025 = profit_2025 * target_pe
        cap_2026 = profit_2026 * target_pe
        
        # 目标价
        shares = self.target_base["total_shares"]
        price_2025 = cap_2025 * 1e8 / shares
        price_2026 = cap_2026 * 1e8 / shares
        
        return {
            "parameters": params,
            "revenue": {
                "2024": base_rev,
                "2025": revenue_2025,
                "2026": revenue_2026,
                "growth_2025": rev_growth_2025,
                "growth_2026": rev_growth_2026
            },
            "profit": {
                "2024": base_profit,
                "2025": profit_2025,
                "2026": profit_2026,
                "growth_2025": profit_growth_2025,
                "growth_2026": profit_growth_2026
            },
            "margin": {
                "2024": base_margin,
                "2025": margin_2025,
                "2026": margin_2026
            },
            "valuation": {
                "pe": target_pe,
                "market_cap_2025": cap_2025,
                "market_cap_2026": cap_2026,
                "price_2025": price_2025,
                "price_2026": price_2026
            }
        }


# ============ 使用示例 ============
if __name__ == "__main__":
    print("=" * 70)
    print("光库科技 (300620.SZ) - 经营杠杆+动态PE版业绩预测")
    print("=" * 70)
    
    # 创建预测器
    forecaster = OperatingLeverageForecaster()
    
    # 添加光通信行业标杆
    print("\n【加载行业标杆数据】")
    forecaster.add_benchmark("天孚通信", "300394.SZ", 0.35)
    forecaster.add_benchmark("中际旭创", "300308.SZ", 0.35)
    forecaster.add_benchmark("新易盛", "300502.SZ", 0.30)
    
    # 加载标杆季度数据
    forecaster.load_all_benchmark_data()
    
    # 设置目标企业
    forecaster.set_target(
        code="300620.SZ",
        name="光库科技",
        revenue_2024=8.5,      # 亿元
        profit_2024=1.0,       # 亿元
        total_shares=2.4918e8   # 2.49亿股
    )
    
    # 获取行业参数
    print(f"\n【行业综合参数】")
    params = forecaster.get_industry_parameters()
    print(f"  标杆数量: {params['benchmark_count']}")
    print(f"  行业平均PE: {params['avg_pe']:.1f}x (动态)")
    print(f"  季度营收环比: {params['avg_revenue_qoq']:+.1%}")
    print(f"  季度利润环比: {params['avg_profit_qoq']:+.1%}")
    print(f"  经营杠杆系数: {params['avg_operating_leverage']:.2f}")
    print(f"  行业平均净利率: {params['avg_profit_margin']:.1%}")
    
    # 执行预测
    print(f"\n【经营杠杆预测模型】")
    print(f"  假设: 固定成本不变，变动成本随营收线性变化")
    print(f"  公式: 利润增速 = 营收增速 × 经营杠杆系数")
    
    result = forecaster.forecast_2025_2026(market_share_change=0)
    
    print(f"\n【业绩预测结果】")
    print(f"2024年: 营收{result['revenue']['2024']:.1f}亿, 净利润{result['profit']['2024']:.2f}亿, 净利率{result['margin']['2024']:.1%}")
    print(f"2025年: 营收{result['revenue']['2025']:.1f}亿(+{result['revenue']['growth_2025']:.0%}), 净利润{result['profit']['2025']:.2f}亿(+{result['profit']['growth_2025']:.0%}), 净利率{result['margin']['2025']:.1%}")
    print(f"2026年: 营收{result['revenue']['2026']:.1f}亿(+{result['revenue']['growth_2026']:.0%}), 净利润{result['profit']['2026']:.2f}亿(+{result['profit']['growth_2026']:.0%}), 净利率{result['margin']['2026']:.1%}")
    
    print(f"\n【动态PE估值】")
    print(f"  使用行业最新PE: {result['valuation']['pe']:.1f}x")
    print(f"  2025年目标市值: {result['valuation']['market_cap_2025']:.1f}亿元")
    print(f"  2026年目标市值: {result['valuation']['market_cap_2026']:.1f}亿元")
    print(f"  2025年目标价: {result['valuation']['price_2025']:.2f}元")
    print(f"  2026年目标价: {result['valuation']['price_2026']:.2f}元")
    
    # 与当前价对比
    current_price = 163.05
    current_cap = 406.3
    print(f"\n【估值对比】")
    print(f"  当前股价: {current_price}元")
    print(f"  当前市值: {current_cap}亿元")
    print(f"  2026目标市值: {result['valuation']['market_cap_2026']:.1f}亿元")
    upside = (result['valuation']['market_cap_2026'] - current_cap) / current_cap * 100
    print(f"  空间: {upside:+.1f}%")
    
    print(f"\n" + "=" * 70)
