#!/root/.openclaw/workspace/venv/bin/python3
"""
个股盈利预测工具 v4.0 - 通用行业版
基于任意行业标杆企业对比的盈利预测工具
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# 配置路径
CONFIG_DIR = Path(__file__).parent.parent / "stock-earnings-forecast" / "config"
INDUSTRIES_CONFIG = CONFIG_DIR / "industries.json"


@dataclass
class BenchmarkStock:
    """标杆企业数据"""
    name: str           # 公司名称
    code: str          # 股票代码
    weight: float      # 权重
    pe: float = 0      # 当前PE
    revenue_growth: float = 0   # 营收增速
    profit_growth: float = 0    # 净利润增速
    profit_margin: float = 0    # 净利润率


@dataclass
class InstitutionForecast:
    """机构预测数据"""
    institution: str
    revenue_2025: float
    revenue_2026: float
    op_profit_2025: float
    op_profit_2026: float
    net_profit_2025: Optional[float] = None
    net_profit_2026: Optional[float] = None
    
    @property
    def revenue_growth(self) -> float:
        return (self.revenue_2026 - self.revenue_2025) / self.revenue_2025
    
    @property
    def margin_2025(self) -> float:
        return self.op_profit_2025 / self.revenue_2025
    
    @property
    def margin_2026(self) -> float:
        return self.op_profit_2026 / self.revenue_2026
    
    @property
    def margin_expansion(self) -> float:
        return self.margin_2026 - self.margin_2025


class IndustryBenchmarkLoader:
    """行业标杆数据加载器"""
    
    def __init__(self):
        self.industries = self._load_industries()
    
    def _load_industries(self) -> Dict:
        """加载行业配置"""
        if not INDUSTRIES_CONFIG.exists():
            # 返回默认行业配置
            return self._default_industries()
        
        with open(INDUSTRIES_CONFIG, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _default_industries(self) -> Dict:
        """默认行业配置"""
        return {
            "industries": {
                "optical_communication": {
                    "name": "光通信",
                    "benchmarks": [
                        {"name": "天孚通信", "code": "300394.SZ", "weight": 0.25},
                        {"name": "中际旭创", "code": "300308.SZ", "weight": 0.25}
                    ]
                },
                "memory": {
                    "name": "存储芯片",
                    "benchmarks": [
                        {"name": "SK海力士", "code": "000660.KS", "weight": 0.5},
                        {"name": "三星电子", "code": "005930.KS", "weight": 0.5}
                    ]
                }
            }
        }
    
    def list_industries(self) -> List[str]:
        """列出所有支持行业"""
        return list(self.industries.get("industries", {}).keys())
    
    def get_industry(self, industry_key: str) -> Optional[Dict]:
        """获取行业配置"""
        return self.industries.get("industries", {}).get(industry_key)
    
    def get_benchmarks(self, industry_key: str) -> List[BenchmarkStock]:
        """获取行业标杆企业列表"""
        industry = self.get_industry(industry_key)
        if not industry:
            return []
        
        benchmarks = []
        for b in industry.get("benchmarks", []):
            benchmarks.append(BenchmarkStock(
                name=b["name"],
                code=b["code"],
                weight=b.get("weight", 1.0)
            ))
        return benchmarks
    
    def auto_detect_industry(self, keywords: List[str]) -> Optional[str]:
        """根据关键词自动检测行业"""
        industries = self.industries.get("industries", {})
        
        for ind_key, ind_data in industries.items():
            search_kws = ind_data.get("search_keywords", [])
            for kw in keywords:
                if kw.lower() in [s.lower() for s in search_kws]:
                    return ind_key
        return None


class UniversalForecaster:
    """
    通用行业预测器
    
    核心逻辑：
    1. 根据行业加载标杆企业
    2. 获取标杆企业的PE和增速
    3. 基于经营杠杆应用到目标企业
    4. 考虑市占率变化
    """
    
    def __init__(self, industry: str = None):
        self.loader = IndustryBenchmarkLoader()
        self.industry = industry
        self.benchmarks: List[BenchmarkStock] = []
        self.target_code = ""
        self.target_name = ""
        self.target_base = {}
        
    def set_industry(self, industry: str):
        """设置行业"""
        self.industry = industry
        self.benchmarks = self.loader.get_benchmarks(industry)
    
    def set_target(self, code: str, name: str,
                   revenue_2024: float, profit_2024: float,
                   margin_2024: Optional[float] = None):
        """设置目标企业基准数据"""
        self.target_code = code
        self.target_name = name
        self.target_base = {
            "revenue": revenue_2024,
            "profit": profit_2024,
            "margin": margin_2024 or (profit_2024 / revenue_2024)
        }
    
    def add_benchmark_data(self, pe: float = None, 
                          revenue_growth: float = None,
                          profit_growth: float = None,
                          profit_margin: float = None):
        """手动添加标杆企业数据"""
        for b in self.benchmarks:
            if pe:
                b.pe = pe
            if revenue_growth:
                b.revenue_growth = revenue_growth
            if profit_growth:
                b.profit_growth = profit_growth
            if profit_margin:
                b.profit_margin = profit_margin
    
    def get_industry_parameters(self) -> Dict:
        """获取行业平均参数"""
        if not self.benchmarks:
            return {}
        
        total_weight = sum(b.weight for b in self.benchmarks)
        
        # 加权平均PE
        avg_pe = sum(b.pe * b.weight for b in self.benchmarks if b.pe) / total_weight
        
        # 加权平均增速
        avg_rev_growth = sum(b.revenue_growth * b.weight for b in self.benchmarks if b.revenue_growth) / total_weight
        avg_profit_growth = sum(b.profit_growth * b.weight for b in self.benchmarks if b.profit_growth) / total_weight
        
        # 加权平均利润率
        avg_margin = sum(b.profit_margin * b.weight for b in self.benchmarks if b.profit_margin) / total_weight
        
        return {
            "avg_pe": avg_pe if avg_pe > 0 else 35,  # 默认35x
            "avg_revenue_growth": avg_rev_growth,
            "avg_profit_growth": avg_profit_growth,
            "avg_profit_margin": avg_margin,
            "benchmark_count": len(self.benchmarks)
        }
    
    def forecast(self, market_share_change: float = 0,
                  margin_adjustment: float = 0) -> Dict:
        """
        执行预测
        
        Args:
            market_share_change: 市占率变化（如0.1表示+10%）
            margin_adjustment: 利润率调整（如0.02表示+2pct）
        
        Returns:
            预测结果字典
        """
        if not self.target_base:
            raise ValueError("请先设置目标企业数据 set_target()")
        
        # 获取行业参数
        ind_params = self.get_industry_parameters()
        
        # 基准数据
        base_revenue = self.target_base["revenue"]
        base_profit = self.target_base["profit"]
        base_margin = self.target_base["margin"]
        
        # 预测2025年
        ind_rev_growth = ind_params.get("avg_revenue_growth", 0.3)
        revenue_2025 = base_revenue * (1 + ind_rev_growth * (1 + market_share_change))
        
        # 利润率调整
        ind_margin = ind_params.get("avg_profit_margin", 0.15)
        margin_2025 = min(base_margin + margin_adjustment, ind_margin)  # 不会超过行业平均
        profit_2025 = revenue_2025 * margin_2025
        
        # 预测2026年
        revenue_2026 = revenue_2025 * (1 + ind_rev_growth * 0.8)  # 增速放缓
        margin_2026 = min(margin_2025 * 1.1, ind_margin * 1.05)  # 利润率继续改善
        profit_2026 = revenue_2026 * margin_2026
        
        # 计算PE（使用行业平均PE）
        target_pe = ind_params.get("avg_pe", 35)
        
        # 目标市值
        cap_2025 = profit_2025 * target_pe
        cap_2026 = profit_2026 * target_pe
        
        # 目标价
        shares = self.target_base.get("shares", 1e8)  # 默认1亿股
        price_2025 = cap_2025 * 1e8 / shares
        price_2026 = cap_2026 * 1e8 / shares
        
        return {
            "forecast_type": "universal_industry_calibrated",
            "industry": self.industry,
            "benchmarks": [b.name for b in self.benchmarks],
            "parameters": ind_params,
            "revenue": {
                "2024": base_revenue,
                "2025": revenue_2025,
                "2026": revenue_2026,
                "growth_2025": (revenue_2025 - base_revenue) / base_revenue,
                "growth_2026": (revenue_2026 - revenue_2025) / revenue_2025
            },
            "profit": {
                "2024": base_profit,
                "2025": profit_2025,
                "2026": profit_2026,
                "growth_2025": (profit_2025 - base_profit) / base_profit,
                "growth_2026": (profit_2026 - profit_2025) / profit_2025
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


def load_industry_benchmarks(industry: str) -> List[BenchmarkStock]:
    """便捷函数：加载行业标杆"""
    loader = IndustryBenchmarkLoader()
    return loader.get_benchmarks(industry)


def quick_forecast(industry: str, code: str, name: str,
                   revenue_2024: float, profit_2024: float,
                   benchmark_data: Dict,
                   total_shares: float = 1e8) -> Dict:
    """
    快速预测函数
    
    Args:
        industry: 行业key (如 "optical_communication")
        code: 目标股票代码
        name: 目标公司名称
        revenue_2024: 2024年营收（亿元）
        profit_2024: 2024年净利润（亿元）
        benchmark_data: 标杆企业数据，如:
            {
                "天孚通信": {"pe": 45, "profit_growth": 0.5, "profit_margin": 0.30},
                "中际旭创": {"pe": 35, "profit_growth": 0.6, "profit_margin": 0.25}
            }
        total_shares: 总股本（股），默认1亿股
    
    Returns:
        预测结果字典
    """
    # 创建预测器
    forecaster = UniversalForecaster(industry)
    forecaster.set_target(code, name, revenue_2024, profit_2024)
    forecaster.target_base["shares"] = total_shares
    
    # 添加标杆数据 - 直接从benchmark_data创建
    bench_count = len(benchmark_data)
    for i, (bench_name, data) in enumerate(benchmark_data.items()):
        b = BenchmarkStock(
            name=bench_name,
            code="",
            weight=1.0 / bench_count
        )
        b.pe = data.get("pe", 35)
        # 使用profit_growth作为revenue_growth的近似
        b.revenue_growth = data.get("profit_growth", 0.3)  
        b.profit_growth = data.get("profit_growth", 0.3)
        b.profit_margin = data.get("profit_margin", 0.15)
        forecaster.benchmarks.append(b)
    
    return forecaster.forecast()


# ============ 使用示例 ============
if __name__ == "__main__":
    # 方式1：使用光通信行业标杆
    print("=" * 60)
    print("光库科技 (300620.SZ) - 通用行业版业绩预测")
    print("=" * 60)
    
    # 光通信标杆数据（基于公开信息）
    optical_benchmarks = {
        "天孚通信": {"pe": 45, "profit_growth": 0.50, "profit_margin": 0.30},
        "中际旭创": {"pe": 35, "profit_growth": 0.60, "profit_margin": 0.25},
        "新易盛": {"pe": 40, "profit_growth": 0.55, "profit_margin": 0.22}
    }
    
    result = quick_forecast(
        industry="optical_communication",
        code="300620.SZ",
        name="光库科技",
        revenue_2024=8.5,   # 亿元
        profit_2024=1.0,    # 亿元
        benchmark_data=optical_benchmarks,
        total_shares=2.4918e8  # 2.49亿股
    )
    
    print(f"\n行业: {result['industry']}")
    print(f"标杆: {', '.join(result['benchmarks'])}")
    print(f"行业平均PE: {result['parameters']['avg_pe']:.1f}x")
    print(f"行业平均净利润率: {result['parameters']['avg_profit_margin']:.1%}")
    
    print(f"\n【业绩预测】")
    print(f"2024年: 营收 {result['revenue']['2024']:.1f}亿, 净利润 {result['profit']['2024']:.2f}亿")
    print(f"2025年: 营收 {result['revenue']['2025']:.1f}亿 (+{result['revenue']['growth_2025']:.0%}), 净利润 {result['profit']['2025']:.2f}亿 (+{result['profit']['growth_2025']:.0%})")
    print(f"2026年: 营收 {result['revenue']['2026']:.1f}亿 (+{result['revenue']['growth_2026']:.0%}), 净利润 {result['profit']['2026']:.2f}亿 (+{result['profit']['growth_2026']:.0%})")
    
    print(f"\n【估值预测】(PE: {result['valuation']['pe']:.1f}x)")
    print(f"2025年目标市值: {result['valuation']['market_cap_2025']:.1f}亿元")
    print(f"2026年目标市值: {result['valuation']['market_cap_2026']:.1f}亿元")
