#!/root/.openclaw/workspace/venv/bin/python3
"""
个股盈利预测工具
支持季度预测（QoQ）和年度预测（YoY）两种时间维度

使用示例:
    # 季度预测
    qf = QuarterlyForecaster()
    qf.set_target("688629.SH", "长鑫科技", q4_revenue=229, q4_profit=85)
    result = qf.forecast()
    
    # 年度预测
    af = AnnualForecaster()
    af.set_target("688629.SH", "长鑫科技", y2025_revenue=550, y2025_profit=30)
    result = af.forecast()
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class BusinessLogic:
    """商业逻辑因子"""
    name: str
    description: str
    impact: float  # 影响系数
    confidence: float  # 置信度 0-1
    
    def effective_impact(self) -> float:
        return self.impact * self.confidence


@dataclass
class BenchmarkQoQ:
    """标杆企业季度环比数据"""
    name: str
    q4_revenue: Optional[float]
    q4_profit: Optional[float]
    q1e_revenue: Optional[float]
    q1e_profit: Optional[float]
    revenue_qoq: Optional[float] = None
    profit_qoq: Optional[float] = None


@dataclass
class BenchmarkYoY:
    """标杆企业年度同比数据"""
    name: str
    y2025_revenue: Optional[float]
    y2025_profit: Optional[float]
    y2026e_revenue: Optional[float]
    y2026e_profit: Optional[float]
    revenue_yoy: Optional[float] = None
    profit_yoy: Optional[float] = None


class QuarterlyForecaster:
    """
    季度预测器（基于环比QoQ）
    
    适用于：下一季度业绩预测、财报季前瞻
    """
    
    def __init__(self):
        self.target_code = ""
        self.target_name = ""
        self.q4_revenue: Optional[float] = None
        self.q4_profit: Optional[float] = None
        self.q4_fixed_cost: Optional[float] = None
        self.benchmarks: List[BenchmarkQoQ] = []
        self.logics: List[BusinessLogic] = []
        
    def set_target(self, code: str, name: str, 
                   q4_revenue: Optional[float] = None,
                   q4_profit: Optional[float] = None,
                   q4_fixed_cost: Optional[float] = None):
        """设置目标企业Q4基准数据"""
        self.target_code = code
        self.target_name = name
        self.q4_revenue = q4_revenue
        self.q4_profit = q4_profit
        self.q4_fixed_cost = q4_fixed_cost
        
    def add_benchmark(self, name: str,
                      q4_revenue: Optional[float] = None,
                      q4_profit: Optional[float] = None,
                      q1e_revenue: Optional[float] = None,
                      q1e_profit: Optional[float] = None):
        """添加标杆企业季度数据"""
        bm = BenchmarkQoQ(name, q4_revenue, q4_profit, q1e_revenue, q1e_profit)
        # 计算环比
        if q4_revenue and q1e_revenue:
            bm.revenue_qoq = (q1e_revenue - q4_revenue) / q4_revenue
        if q4_profit and q1e_profit:
            bm.profit_qoq = (q1e_profit - q4_profit) / q4_profit
        self.benchmarks.append(bm)
        
    def add_logic(self, name: str, impact: float, confidence: float, description: str = ""):
        """添加商业逻辑因子"""
        self.logics.append(BusinessLogic(name, description, impact, confidence))
        
    def forecast(self) -> Dict:
        """执行季度预测"""
        if not self.q4_profit:
            raise ValueError("目标企业Q4利润未设置")
        if not self.benchmarks:
            raise ValueError("未添加标杆企业")
            
        # 1. 计算调整系数
        adjustment = 1.0
        for logic in self.logics:
            adjustment *= (1 + logic.effective_impact())
            
        # 2. 获取标杆平均环比
        avg_profit_qoq = sum([b.profit_qoq for b in self.benchmarks if b.profit_qoq]) / \
                         len([b for b in self.benchmarks if b.profit_qoq])
        
        # 3. 调整后环比涨幅
        adjusted_qoq = avg_profit_qoq * adjustment
        
        # 4. 预测Q1利润
        q1_profit = self.q4_profit * (1 + adjusted_qoq)
        
        # 5. 营收预测（如有数据）
        q1_revenue = None
        revenue_qoq = None
        if self.q4_revenue:
            revenue_benchmarks = [b for b in self.benchmarks if b.revenue_qoq]
            if revenue_benchmarks:
                avg_revenue_qoq = sum([b.revenue_qoq for b in revenue_benchmarks]) / len(revenue_benchmarks)
                revenue_qoq = avg_revenue_qoq * adjustment
                q1_revenue = self.q4_revenue * (1 + revenue_qoq)
        
        return {
            "forecast_type": "quarterly",
            "period": "2026Q1",
            "base_quarter": "2025Q4",
            "revenue": {
                "q4_actual": self.q4_revenue,
                "q1_forecast": round(q1_revenue, 2) if q1_revenue else None,
                "qoq_growth": round(revenue_qoq, 4) if revenue_qoq else None
            },
            "profit": {
                "q4_actual": self.q4_profit,
                "q1_forecast": round(q1_profit, 2),
                "q1_range": [round(q1_profit * 0.85, 2), round(q1_profit * 1.15, 2)],
                "qoq_growth": round(adjusted_qoq, 4)
            },
            "methodology": {
                "benchmark_avg_qoq": round(avg_profit_qoq, 4),
                "adjustment_factor": round(adjustment, 4),
                "adjusted_qoq": round(adjusted_qoq, 4)
            },
            "logic_breakdown": {logic.name: round(logic.effective_impact(), 4) for logic in self.logics}
        }


class AnnualForecaster:
    """
    年度预测器（基于同比YoY）
    
    适用于：全年业绩预测、年度投资规划
    """
    
    def __init__(self):
        self.target_code = ""
        self.target_name = ""
        self.y2025_revenue: Optional[float] = None
        self.y2025_profit: Optional[float] = None
        self.y2025_fixed_cost: Optional[float] = None
        self.q4_profit: Optional[float] = None  # Q4单季度利润（用于年化）
        self.benchmarks: List[BenchmarkYoY] = []
        self.logics: List[BusinessLogic] = []
        
    def set_target(self, code: str, name: str,
                   y2025_revenue: Optional[float] = None,
                   y2025_profit: Optional[float] = None,
                   y2025_fixed_cost: Optional[float] = None,
                   q4_profit: Optional[float] = None):
        """
        设置目标企业2025年基准数据
        
        Args:
            y2025_profit: 2025年全年利润（对于扭亏企业可能偏低）
            q4_profit: Q4单季度利润（用于年化计算，更准确）
        """
        self.target_code = code
        self.target_name = name
        self.y2025_revenue = y2025_revenue
        self.y2025_profit = y2025_profit
        self.y2025_fixed_cost = y2025_fixed_cost
        self.q4_profit = q4_profit
        
    def add_benchmark(self, name: str,
                      y2025_revenue: Optional[float] = None,
                      y2025_profit: Optional[float] = None,
                      y2026e_revenue: Optional[float] = None,
                      y2026e_profit: Optional[float] = None):
        """添加标杆企业年度数据"""
        bm = BenchmarkYoY(name, y2025_revenue, y2025_profit, y2026e_revenue, y2026e_profit)
        # 计算同比
        if y2025_revenue and y2026e_revenue:
            bm.revenue_yoy = (y2026e_revenue - y2025_revenue) / y2025_revenue
        if y2025_profit and y2026e_profit:
            bm.profit_yoy = (y2026e_profit - y2025_profit) / y2025_profit
        self.benchmarks.append(bm)
        
    def add_logic(self, name: str, impact: float, confidence: float, description: str = ""):
        """添加商业逻辑因子"""
        self.logics.append(BusinessLogic(name, description, impact, confidence))
        
    def forecast(self) -> Dict:
        """执行年度预测（基于Q4年化利润）"""
        if not self.benchmarks:
            raise ValueError("未添加标杆企业")
        
        # 使用Q4利润年化作为基数（更准确反映当前盈利能力）
        if self.q4_profit:
            base_profit = self.q4_profit * 4  # Q4年化
            base_desc = f"Q4年化({self.q4_profit}×4={base_profit})"
        elif self.y2025_profit:
            base_profit = self.y2025_profit
            base_desc = f"全年利润({base_profit})"
        else:
            raise ValueError("目标企业利润未设置（需要提供q4_profit或y2025_profit）")
            
        # 1. 计算调整系数（年度逻辑影响通常更大）
        adjustment = 1.0
        for logic in self.logics:
            adjustment *= (1 + logic.effective_impact())
            
        # 2. 获取标杆平均同比
        avg_profit_yoy = sum([b.profit_yoy for b in self.benchmarks if b.profit_yoy]) / \
                         len([b for b in self.benchmarks if b.profit_yoy])
        
        # 3. 调整后同比涨幅
        adjusted_yoy = avg_profit_yoy * adjustment
        
        # 4. 预测2026年利润（基于Q4年化基数）
        y2026_profit = base_profit * (1 + adjusted_yoy)
        
        # 5. 营收预测
        y2026_revenue = None
        revenue_yoy = None
        if self.y2025_revenue:
            revenue_benchmarks = [b for b in self.benchmarks if b.revenue_yoy]
            if revenue_benchmarks:
                avg_revenue_yoy = sum([b.revenue_yoy for b in revenue_benchmarks]) / len(revenue_benchmarks)
                revenue_yoy = avg_revenue_yoy * adjustment
                y2026_revenue = self.y2025_revenue * (1 + revenue_yoy)
        
        return {
            "forecast_type": "annual",
            "period": "2026E",
            "base_year": "2025A",
            "base_profit": {
                "value": round(base_profit, 2),
                "source": base_desc
            },
            "revenue": {
                "2025_actual": self.y2025_revenue,
                "2026_forecast": round(y2026_revenue, 2) if y2026_revenue else None,
                "yoy_growth": round(revenue_yoy, 4) if revenue_yoy else None
            },
            "profit": {
                "2025_actual": self.y2025_profit,
                "2026_forecast": round(y2026_profit, 2),
                "2026_range": [round(y2026_profit * 0.8, 2), round(y2026_profit * 1.2, 2)],
                "yoy_growth": round(adjusted_yoy, 4)
            },
            "methodology": {
                "benchmark_avg_yoy": round(avg_profit_yoy, 4),
                "adjustment_factor": round(adjustment, 4),
                "adjusted_yoy": round(adjusted_yoy, 4)
            },
            "logic_breakdown": {logic.name: round(logic.effective_impact(), 4) for logic in self.logics}
        }


class IndustryDrivenForecaster:
    """
    行业数据驱动预测器
    支持季度和年度两种时间维度
    """
    
    def forecast_quarterly(self, 
                          q4_revenue: float,
                          q4_material_cost: float,
                          q4_fixed_cost: float,
                          gross_margin: float,
                          industry_qoq: float,
                          market_share_change: float) -> Dict:
        """
        季度预测（行业数据驱动）
        
        Args:
            q4_revenue: Q4营收
            q4_material_cost: Q4原材料成本
            q4_fixed_cost: Q4固定成本（季度）
            gross_margin: 毛利率
            industry_qoq: 行业环比增幅
            market_share_change: 市占率变化
        """
        # 营收增幅 = 行业增幅 × 市占率系数
        revenue_growth = industry_qoq * (1 + market_share_change)
        
        # Q1预测
        q1_revenue = q4_revenue * (1 + revenue_growth)
        q1_material = q4_material_cost * (1 + revenue_growth)
        q1_gross_profit = q1_revenue * gross_margin
        q1_operating_profit = q1_gross_profit - q4_fixed_cost
        q1_net_profit = q1_operating_profit * 0.85  # 税后
        
        return {
            "forecast_type": "quarterly_industry_driven",
            "q1_revenue": round(q1_revenue, 2),
            "q1_net_profit": round(q1_net_profit, 2),
            "revenue_qoq": round(revenue_growth, 4),
            "cost_structure": {
                "material_cost": round(q1_material, 2),
                "fixed_cost": q4_fixed_cost,
                "gross_profit": round(q1_gross_profit, 2)
            }
        }
    
    def forecast_annual(self,
                       y2025_revenue: float,
                       y2025_material_cost: float,
                       y2025_fixed_cost: float,
                       gross_margin: float,
                       industry_yoy: float,
                       market_share_change: float) -> Dict:
        """
        年度预测（行业数据驱动）
        
        Args:
            y2025_revenue: 2025年营收
            y2025_material_cost: 2025年原材料成本
            y2025_fixed_cost: 2025年固定成本（全年）
            gross_margin: 毛利率
            industry_yoy: 行业同比增幅
            market_share_change: 市占率变化
        """
        # 营收增幅 = 行业增幅 × 市占率系数
        revenue_growth = industry_yoy * (1 + market_share_change)
        
        # 2026年预测
        y2026_revenue = y2025_revenue * (1 + revenue_growth)
        y2026_material = y2025_material_cost * (1 + revenue_growth)
        y2026_gross_profit = y2026_revenue * gross_margin
        y2026_operating_profit = y2026_gross_profit - y2025_fixed_cost
        y2026_net_profit = y2026_operating_profit * 0.85
        
        return {
            "forecast_type": "annual_industry_driven",
            "2026_revenue": round(y2026_revenue, 2),
            "2026_net_profit": round(y2026_net_profit, 2),
            "revenue_yoy": round(revenue_growth, 4),
            "cost_structure": {
                "material_cost": round(y2026_material, 2),
                "fixed_cost": y2025_fixed_cost,
                "gross_profit": round(y2026_gross_profit, 2)
            }
        }


def example_quarterly():
    """季度预测示例"""
    print("="*70)
    print("季度预测示例：长鑫科技 2026Q1")
    print("="*70)
    
    qf = QuarterlyForecaster()
    qf.set_target("688629.SH", "长鑫科技", 
                  q4_revenue=229, q4_profit=85, q4_fixed_cost=25)
    
    qf.add_benchmark("SK海力士", 
                    q4_profit=15.25, q1e_profit=29.0)
    
    qf.add_logic("产能转移", 0.25, 0.9, "海力士转产HBM")
    qf.add_logic("国产替代", 0.15, 0.85, "华为/中兴导入")
    qf.add_logic("价格趋势", 0.10, 0.8, "DRAM涨价")
    qf.add_logic("季节性", -0.05, 0.6, "春节影响")
    
    result = qf.forecast()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def example_annual():
    """年度预测示例"""
    print("\n" + "="*70)
    print("年度预测示例：长鑫科技 2026E")
    print("="*70)
    
    af = AnnualForecaster()
    # 关键修正：提供q4_profit用于年化计算
    af.set_target("688629.SH", "长鑫科技",
                  y2025_revenue=550, y2025_profit=30, 
                  y2025_fixed_cost=100, q4_profit=85)  # 新增q4_profit
    
    af.add_benchmark("SK海力士",
                    y2025_profit=42.95, y2026e_profit=185)
    
    af.add_logic("产能转移", 0.30, 0.9, "海力士转产HBM持续")
    af.add_logic("国产替代", 0.25, 0.85, "国产替代加速")
    af.add_logic("产能释放", 0.25, 0.8, "3座工厂爬坡")
    
    result = af.forecast()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def example_industry_quarterly():
    """行业数据驱动季度预测"""
    print("\n" + "="*70)
    print("行业数据驱动季度预测：长鑫科技 2026Q1")
    print("="*70)
    
    idf = IndustryDrivenForecaster()
    result = idf.forecast_quarterly(
        q4_revenue=229,
        q4_material_cost=120,
        q4_fixed_cost=25,  # 季度固定成本
        gross_margin=0.35,
        industry_qoq=0.10,  # 行业环比+10%
        market_share_change=0.10  # 市占率+10%
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


def example_industry_annual():
    """行业数据驱动年度预测"""
    print("\n" + "="*70)
    print("行业数据驱动年度预测：长鑫科技 2026E")
    print("="*70)
    
    idf = IndustryDrivenForecaster()
    result = idf.forecast_annual(
        y2025_revenue=550,
        y2025_material_cost=280,
        y2025_fixed_cost=100,  # 年度固定成本
        gross_margin=0.35,
        industry_yoy=0.30,  # 行业同比+30%
        market_share_change=0.30  # 市占率+30%（7%→10%）
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    example_quarterly()
    example_annual()
    example_industry_quarterly()
    example_industry_annual()
