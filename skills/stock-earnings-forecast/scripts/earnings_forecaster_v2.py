#!/root/.openclaw/workspace/venv/bin/python3
"""
个股盈利预测工具 v2.0 - 经营杠杆优化版
支持季度预测（QoQ）和年度预测（YoY）
核心改进：营收增长时净利润率提升（固定成本不变）
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class BusinessLogic:
    """商业逻辑因子"""
    name: str
    description: str
    impact: float
    confidence: float
    
    def effective_impact(self) -> float:
        return self.impact * self.confidence


class OperatingLeverageForecaster:
    """
    经营杠杆预测器（核心类）
    
    核心假设：
    - 固定成本（折旧、研发、管理）不随营收变化
    - 变动成本（原材料）随营收线性增长
    - 营收增长 → 经营杠杆释放 → 净利润率提升
    """
    
    def __init__(self):
        self.target_code = ""
        self.target_name = ""
        self.base_revenue: Optional[float] = None
        self.base_profit: Optional[float] = None
        self.base_fixed_cost: Optional[float] = None
        self.base_material_cost: Optional[float] = None
        self.base_gross_margin: Optional[float] = None
        
    def set_target(self, code: str, name: str,
                   base_revenue: float,
                   base_profit: float,
                   base_fixed_cost: float,
                   base_material_cost: Optional[float] = None,
                   base_gross_margin: Optional[float] = None):
        """
        设置目标企业基准数据
        
        Args:
            base_revenue: 基准营收（Q4或全年）
            base_profit: 基准净利润
            base_fixed_cost: 基准固定成本（季度或年度）
            base_material_cost: 原材料成本（可选）
            base_gross_margin: 毛利率（可选，用于计算原材料成本）
        """
        self.target_code = code
        self.target_name = name
        self.base_revenue = base_revenue
        self.base_profit = base_profit
        self.base_fixed_cost = base_fixed_cost
        self.base_gross_margin = base_gross_margin
        
        # 计算或设置原材料成本
        if base_material_cost:
            self.base_material_cost = base_material_cost
        elif base_gross_margin:
            gross_profit = base_revenue * base_gross_margin
            # 原材料成本 = 营收 - 毛利 - 其他变动成本（简化）
            # 假设原材料占营收的50-60%
            self.base_material_cost = base_revenue * 0.55
        else:
            # 反推：从利润反推成本结构
            # 净利润 = 毛利 - 固定成本
            # 假设税率15%，其他收益10%
            operating_profit = base_profit / 0.935  # 还原税前
            gross_profit = operating_profit + base_fixed_cost
            self.base_material_cost = base_revenue - gross_profit
            self.base_gross_margin = gross_profit / base_revenue
    
    def calculate_profit_margin_expansion(self, revenue_growth: float) -> Tuple[float, float, float]:
        """
        计算营收增长后的利润（经营杠杆效应）
        
        Args:
            revenue_growth: 营收增长率（如0.20表示+20%）
            
        Returns:
            (预测营收, 预测利润, 预测净利润率)
        """
        # 1. 预测营收
        forecast_revenue = self.base_revenue * (1 + revenue_growth)
        
        # 2. 变动成本（原材料）随营收线性增长
        forecast_material_cost = self.base_material_cost * (1 + revenue_growth)
        
        # 3. 固定成本不变（经营杠杆核心）
        forecast_fixed_cost = self.base_fixed_cost
        
        # 4. 计算毛利和营业利润
        forecast_gross_profit = forecast_revenue - forecast_material_cost
        forecast_operating_profit = forecast_gross_profit - forecast_fixed_cost
        
        # 5. 计算净利润（税率15%，其他收益10%）
        forecast_net_profit = forecast_operating_profit * 0.85 * 1.1
        
        # 6. 净利润率
        forecast_profit_margin = forecast_net_profit / forecast_revenue
        
        return forecast_revenue, forecast_net_profit, forecast_profit_margin
    
    def forecast_quarterly(self, 
                          revenue_qoq: float,
                          market_share_change: float = 0) -> Dict:
        """
        季度预测
        
        Args:
            revenue_qoq: 行业营收环比增幅
            market_share_change: 市占率变化（如0.10表示+10%）
        """
        # 综合营收增幅 = 行业增幅 + 市占率提升
        total_revenue_growth = revenue_qoq * (1 + market_share_change)
        
        forecast_revenue, forecast_profit, forecast_margin = \
            self.calculate_profit_margin_expansion(total_revenue_growth)
        
        # 计算基准净利润率
        base_margin = self.base_profit / self.base_revenue
        
        # 利润率提升幅度
        margin_expansion = forecast_margin - base_margin
        
        return {
            "forecast_type": "quarterly",
            "period": "next_quarter",
            "revenue": {
                "base": round(self.base_revenue, 2),
                "forecast": round(forecast_revenue, 2),
                "qoq_growth": round(total_revenue_growth, 4),
                "industry_qoq": round(revenue_qoq, 4),
                "market_share_impact": round(market_share_change, 4)
            },
            "profit": {
                "base": round(self.base_profit, 2),
                "forecast": round(forecast_profit, 2),
                "forecast_range": [round(forecast_profit * 0.85, 2), round(forecast_profit * 1.15, 2)]
            },
            "margin_analysis": {
                "base_margin": round(base_margin * 100, 2),
                "forecast_margin": round(forecast_margin * 100, 2),
                "margin_expansion": round(margin_expansion * 100, 2)
            },
            "cost_structure": {
                "base_material_cost": round(self.base_material_cost, 2),
                "base_fixed_cost": round(self.base_fixed_cost, 2),
                "forecast_material_cost": round(self.base_material_cost * (1 + total_revenue_growth), 2),
                "forecast_fixed_cost": round(self.base_fixed_cost, 2)
            },
            "operating_leverage": {
                "description": "固定成本不变，营收增长带来利润率提升",
                "leverage_effect": f"利润率从{base_margin*100:.1f}%提升至{forecast_margin*100:.1f}%"
            }
        }
    
    def forecast_annual(self,
                       revenue_yoy: float,
                       market_share_change: float = 0) -> Dict:
        """
        年度预测
        
        Args:
            revenue_yoy: 行业营收同比增幅
            market_share_change: 市占率变化
        """
        # 综合营收增幅
        total_revenue_growth = revenue_yoy * (1 + market_share_change)
        
        forecast_revenue, forecast_profit, forecast_margin = \
            self.calculate_profit_margin_expansion(total_revenue_growth)
        
        base_margin = self.base_profit / self.base_revenue
        margin_expansion = forecast_margin - base_margin
        
        return {
            "forecast_type": "annual",
            "period": "2026E",
            "revenue": {
                "base_2025": round(self.base_revenue, 2),
                "forecast_2026": round(forecast_revenue, 2),
                "yoy_growth": round(total_revenue_growth, 4),
                "industry_yoy": round(revenue_yoy, 4),
                "market_share_impact": round(market_share_change, 4)
            },
            "profit": {
                "base_2025": round(self.base_profit, 2),
                "forecast_2026": round(forecast_profit, 2),
                "forecast_range": [round(forecast_profit * 0.8, 2), round(forecast_profit * 1.2, 2)]
            },
            "margin_analysis": {
                "base_margin": round(base_margin * 100, 2),
                "forecast_margin": round(forecast_margin * 100, 2),
                "margin_expansion": round(margin_expansion * 100, 2)
            },
            "cost_structure": {
                "base_material_cost": round(self.base_material_cost, 2),
                "base_fixed_cost": round(self.base_fixed_cost, 2),
                "forecast_material_cost": round(self.base_material_cost * (1 + total_revenue_growth), 2),
                "forecast_fixed_cost": round(self.base_fixed_cost, 2)
            },
            "operating_leverage": {
                "description": "固定成本不变，营收增长带来利润率提升",
                "leverage_effect": f"利润率从{base_margin*100:.1f}%提升至{forecast_margin*100:.1f}%"
            }
        }


class BenchmarkForecaster:
    """
    标杆对比预测器（改进版）
    
    改进：标杆涨幅仅用于预测营收，利润通过经营杠杆计算
    """
    
    def __init__(self):
        self.target_code = ""
        self.target_name = ""
        self.target_base = {}  # 目标企业基准数据
        self.benchmarks: List[Dict] = []
        self.logics: List[BusinessLogic] = []
        
    def set_target(self, code: str, name: str,
                   base_revenue: float,
                   base_profit: float,
                   base_fixed_cost: float):
        """设置目标企业"""
        self.target_code = code
        self.target_name = name
        self.target_base = {
            "revenue": base_revenue,
            "profit": base_profit,
            "fixed_cost": base_fixed_cost
        }
        
    def add_benchmark(self, name: str,
                      base_revenue: float,
                      base_profit: float,
                      forecast_revenue: float,
                      forecast_profit: float):
        """添加标杆企业"""
        revenue_growth = (forecast_revenue - base_revenue) / base_revenue
        profit_growth = (forecast_profit - base_profit) / base_profit
        self.benchmarks.append({
            "name": name,
            "revenue_growth": revenue_growth,
            "profit_growth": profit_growth
        })
        
    def add_logic(self, name: str, impact: float, confidence: float):
        """添加商业逻辑"""
        self.logics.append(BusinessLogic(name, "", impact, confidence))
        
    def forecast(self, forecast_type: str = "quarterly") -> Dict:
        """
        执行预测
        
        Args:
            forecast_type: "quarterly" 或 "annual"
        """
        # 1. 计算标杆平均营收涨幅
        avg_revenue_growth = sum([b["revenue_growth"] for b in self.benchmarks]) / len(self.benchmarks)
        
        # 2. 计算调整系数
        adjustment = 1.0
        for logic in self.logics:
            adjustment *= (1 + logic.effective_impact())
        
        # 3. 调整后营收涨幅
        adjusted_revenue_growth = avg_revenue_growth * adjustment
        
        # 4. 使用经营杠杆预测器计算利润
        olf = OperatingLeverageForecaster()
        olf.set_target(
            self.target_code,
            self.target_name,
            base_revenue=self.target_base["revenue"],
            base_profit=self.target_base["profit"],
            base_fixed_cost=self.target_base["fixed_cost"]
        )
        
        if forecast_type == "quarterly":
            result = olf.forecast_quarterly(adjusted_revenue_growth)
        else:
            result = olf.forecast_annual(adjusted_revenue_growth)
        
        # 添加标杆信息
        result["benchmark"] = {
            "avg_revenue_growth": round(avg_revenue_growth, 4),
            "adjustment_factor": round(adjustment, 4),
            "adjusted_revenue_growth": round(adjusted_revenue_growth, 4),
            "logic_breakdown": {logic.name: round(logic.effective_impact(), 4) for logic in self.logics}
        }
        
        return result


def example_changxin_quarterly():
    """长鑫科技季度预测示例"""
    print("="*70)
    print("长鑫科技 2026Q1 预测（经营杠杆模型）")
    print("="*70)
    
    # 基准数据（Q4）
    forecaster = OperatingLeverageForecaster()
    forecaster.set_target(
        code="688629.SH",
        name="长鑫科技",
        base_revenue=229,      # Q4营收
        base_profit=85,        # Q4净利润
        base_fixed_cost=25,    # Q4固定成本（季度）
        base_gross_margin=0.35 # 毛利率35%
    )
    
    # 行业数据：DRAM市场Q1环比+10%，长鑫市占率+10%
    result = forecaster.forecast_quarterly(
        revenue_qoq=0.10,
        market_share_change=0.10
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def example_changxin_annual():
    """长鑫科技年度预测示例"""
    print("\n" + "="*70)
    print("长鑫科技 2026E 预测（经营杠杆模型）")
    print("="*70)
    
    # 基准数据（2025年全年）
    forecaster = OperatingLeverageForecaster()
    forecaster.set_target(
        code="688629.SH",
        name="长鑫科技",
        base_revenue=550,      # 2025全年营收
        base_profit=100,       # 2025全年净利润（假设下半年盈利）
        base_fixed_cost=100,   # 2025全年固定成本
        base_gross_margin=0.35
    )
    
    # 行业数据：DRAM市场2026同比+30%，长鑫市占率+30%（7%→10%）
    result = forecaster.forecast_annual(
        revenue_yoy=0.30,
        market_share_change=0.30
    )
    
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def example_benchmark_method():
    """标杆对比法示例（改进版）"""
    print("\n" + "="*70)
    print("长鑫科技 2026E 预测（标杆对比+经营杠杆）")
    print("="*70)
    
    bf = BenchmarkForecaster()
    bf.set_target(
        code="688629.SH",
        name="长鑫科技",
        base_revenue=550,
        base_profit=100,      # 修正：假设2025下半年已盈利
        base_fixed_cost=100
    )
    
    # SK海力士标杆数据
    bf.add_benchmark(
        name="SK海力士",
        base_revenue=66.9,    # 2025年营收（万亿韩元，约450亿美元）
        base_profit=3.3,      # 2025年利润（万亿韩元）
        forecast_revenue=100.0,  # 2026E营收（万亿韩元）
        forecast_profit=18.5     # 2026E利润（万亿韩元）
    )
    
    # 商业逻辑
    bf.add_logic("产能转移", 0.20, 0.9)
    bf.add_logic("国产替代", 0.15, 0.85)
    bf.add_logic("产能释放", 0.15, 0.8)
    
    result = bf.forecast(forecast_type="annual")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    example_changxin_quarterly()
    example_changxin_annual()
    example_benchmark_method()
