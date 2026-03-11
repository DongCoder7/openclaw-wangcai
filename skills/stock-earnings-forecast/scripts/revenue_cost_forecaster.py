#!/root/.openclaw/workspace/venv/bin/python3
"""
收入-成本模型预测器 v5.0
基于真实财务数据的成本分解和利润预测
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/stock-earnings-forecast/scripts')

from typing import Dict, List, Optional
from dataclasses import dataclass
from financial_data_fetcher import FinancialDataManager, FinancialData


@dataclass
class CostStructure:
    """成本结构"""
    fixed_cost: float        # 固定成本（亿元）
    variable_cost: float     # 变动成本（亿元）
    variable_cost_rate: float  # 变动成本率（变动成本/营收）
    
    def calculate_profit(self, revenue: float) -> float:
        """
        基于成本结构计算利润
        
        公式: 利润 = 营收 - 固定成本 - 变动成本
             变动成本 = 营收 × 变动成本率
        """
        variable = revenue * self.variable_cost_rate
        return revenue - self.fixed_cost - variable


class RevenueCostForecaster:
    """
    收入-成本模型预测器
    
    核心逻辑：
    1. 获取标杆企业真实财务数据（营收、成本、利润）
    2. 分解标杆企业成本结构（固定成本 vs 变动成本）
    3. 计算标杆企业营收增长率
    4. 应用到目标企业：
       - 目标营收 = 基准营收 × (1 + 标杆平均增长率)
       - 目标变动成本 = 目标营收 × 变动成本率
       - 目标固定成本 = 不变（或小幅增长）
       - 目标利润 = 目标营收 - 固定成本 - 变动成本
    5. 不使用PE估值，直接用预测利润计算市值
    """
    
    def __init__(self):
        self.data_manager = FinancialDataManager()
        self.benchmark_data: Dict[str, List[FinancialData]] = {}  # 标杆企业数据
        self.target_code = ""
        self.target_name = ""
        self.target_base: FinancialData = None
        
    def add_benchmark(self, code: str, name: str):
        """添加标杆企业"""
        print(f"加载标杆: {name}({code})")
        data = self.data_manager.get_stock_financials(code, 2024)
        if data:
            self.benchmark_data[code] = data
            # 打印最新季度数据
            latest = data[-1] if data else None
            if latest:
                print(f"  {latest.period}: 营收{latest.revenue:.2f}亿, 净利{latest.net_profit:.2f}亿, 净利率{latest.net_margin:.1%}")
        else:
            print(f"  警告: 未获取到{name}数据")
    
    def set_target(self, code: str, name: str, base_data: FinancialData):
        """设置目标企业"""
        self.target_code = code
        self.target_name = name
        self.target_base = base_data
        print(f"\n目标企业: {name}({code})")
        print(f"基准: {base_data.period} 营收{base_data.revenue:.2f}亿, 净利{base_data.net_profit:.2f}亿")
    
    def analyze_benchmark_growth(self) -> Dict:
        """
        分析标杆企业营收增长率
        
        Returns:
            {
                'avg_revenue_growth': 平均营收增长率,
                'avg_profit_growth': 平均利润增长率,
                'quarterly_trend': 季度趋势
            }
        """
        growth_rates = []
        profit_growth_rates = []
        
        for code, data in self.benchmark_data.items():
            if len(data) >= 2:
                # 计算季度环比增长率
                for i in range(1, len(data)):
                    q0, q1 = data[i-1], data[i]
                    rev_growth = (q1.revenue - q0.revenue) / q0.revenue
                    profit_growth = (q1.net_profit - q0.net_profit) / q0.net_profit if q0.net_profit > 0 else 0
                    growth_rates.append(rev_growth)
                    profit_growth_rates.append(profit_growth)
        
        if not growth_rates:
            return {'avg_revenue_growth': 0.3, 'avg_profit_growth': 0.4}  # 默认30%/40%
        
        import statistics
        return {
            'avg_revenue_growth': statistics.mean(growth_rates),
            'avg_profit_growth': statistics.mean(profit_growth_rates),
            'growth_rates': growth_rates
        }
    
    def analyze_cost_structure(self) -> CostStructure:
        """
        分析标杆企业平均成本结构
        
        Returns:
            CostStructure: 平均成本结构
        """
        fixed_costs = []
        variable_costs = []
        variable_rates = []
        
        for code, data in self.benchmark_data.items():
            for d in data:
                cost_struct = self.data_manager.calculate_cost_structure(d)
                if cost_struct:
                    fixed_costs.append(cost_struct['fixed_cost'])
                    variable_costs.append(cost_struct['variable_cost'])
                    variable_rates.append(cost_struct['variable_cost_rate'])
        
        import statistics
        return CostStructure(
            fixed_cost=statistics.mean(fixed_costs) if fixed_costs else 0,
            variable_cost=statistics.mean(variable_costs) if variable_costs else 0,
            variable_cost_rate=statistics.mean(variable_rates) if variable_rates else 0.6
        )
    
    def forecast_2025_2026(self, market_share_change: float = 0) -> Dict:
        """
        预测2025和2026年业绩
        
        Args:
            market_share_change: 市占率变化（如0.1表示+10%）
        
        Returns:
            预测结果
        """
        print("\n" + "=" * 60)
        print("收入-成本模型预测")
        print("=" * 60)
        
        # 1. 分析标杆增长率
        growth = self.analyze_benchmark_growth()
        print(f"\n【标杆企业分析】")
        print(f"平均营收季度增长率: {growth['avg_revenue_growth']:+.1%}")
        print(f"平均利润季度增长率: {growth['avg_profit_growth']:+.1%}")
        
        # 2. 分析成本结构
        cost_struct = self.analyze_cost_structure()
        print(f"\n【行业成本结构】")
        print(f"平均固定成本: {cost_struct.fixed_cost:.2f}亿")
        print(f"平均变动成本率: {cost_struct.variable_cost_rate:.1%}")
        print(f"公式: 利润 = 营收 - 固定成本 - 变动成本")
        print(f"     变动成本 = 营收 × {cost_struct.variable_cost_rate:.1%}")
        
        # 3. 目标企业基准
        base_revenue = self.target_base.revenue
        base_profit = self.target_base.net_profit
        
        # 4. 估算目标企业当前成本结构
        # 假设目标企业与行业平均成本结构相似
        target_fixed_cost = base_revenue * 0.15  # 估算固定成本占比15%
        target_variable_rate = cost_struct.variable_cost_rate
        
        print(f"\n【目标企业成本结构估算】")
        print(f"基准营收: {base_revenue:.2f}亿")
        print(f"固定成本: {target_fixed_cost:.2f}亿 (估算)")
        print(f"变动成本率: {target_variable_rate:.1%} (行业平均)")
        
        # 验证: 当前利润 = 营收 - 固定 - 变动
        check_profit = base_revenue - target_fixed_cost - (base_revenue * target_variable_rate)
        print(f"验证: {base_revenue:.2f} - {target_fixed_cost:.2f} - {base_revenue * target_variable_rate:.2f} = {check_profit:.2f}亿 (实际{base_profit:.2f}亿)")
        
        # 5. 预测2025年
        # 年化增长率（季度增长率的4次方）
        annual_growth = (1 + growth['avg_revenue_growth']) ** 4 - 1
        rev_growth_2025 = annual_growth * (1 + market_share_change)
        
        revenue_2025 = base_revenue * (1 + rev_growth_2025)
        # 固定成本不变（或小幅增长5%）
        fixed_2025 = target_fixed_cost * 1.05
        # 变动成本随营收线性变化
        variable_2025 = revenue_2025 * target_variable_rate
        profit_2025 = revenue_2025 - fixed_2025 - variable_2025
        
        print(f"\n【2025年预测】")
        print(f"营收: {base_revenue:.2f} × (1+{rev_growth_2025:.1%}) = {revenue_2025:.2f}亿")
        print(f"固定成本: {fixed_2025:.2f}亿 (+5%)")
        print(f"变动成本: {revenue_2025:.2f} × {target_variable_rate:.1%} = {variable_2025:.2f}亿")
        print(f"净利润: {revenue_2025:.2f} - {fixed_2025:.2f} - {variable_2025:.2f} = {profit_2025:.2f}亿")
        
        # 6. 预测2026年（增速放缓20%）
        rev_growth_2026 = rev_growth_2025 * 0.8
        revenue_2026 = revenue_2025 * (1 + rev_growth_2026)
        fixed_2026 = fixed_2025 * 1.03  # 继续小幅增长3%
        variable_2026 = revenue_2026 * target_variable_rate
        profit_2026 = revenue_2026 - fixed_2026 - variable_2026
        
        print(f"\n【2026年预测】")
        print(f"营收: {revenue_2025:.2f} × (1+{rev_growth_2026:.1%}) = {revenue_2026:.2f}亿")
        print(f"固定成本: {fixed_2026:.2f}亿 (+3%)")
        print(f"变动成本: {revenue_2026:.2f} × {target_variable_rate:.1%} = {variable_2026:.2f}亿")
        print(f"净利润: {revenue_2026:.2f} - {fixed_2026:.2f} - {variable_2026:.2f} = {profit_2026:.2f}亿")
        
        # 7. 市值估算（使用行业平均PE作为参考，不是主要估值方法）
        # 这里主要是为了对比，核心估值应该用DCF或PS，但简化用PE参考
        print(f"\n【估值参考】")
        print("注意: 收入-成本模型的核心是预测真实利润，不是PE估值")
        print("以下PE估值仅作参考:")
        
        # 计算行业平均PE（简化，实际应该用真实数据）
        pe_range = [40, 50, 60]  # 光通信行业PE区间
        for pe in pe_range:
            cap = profit_2026 * pe
            print(f"  PE {pe}x: 市值 = {profit_2026:.2f}亿 × {pe} = {cap:.1f}亿元")
        
        return {
            'base': {
                'revenue': base_revenue,
                'profit': base_profit,
                'fixed_cost': target_fixed_cost,
                'variable_rate': target_variable_rate
            },
            '2025': {
                'revenue': revenue_2025,
                'fixed_cost': fixed_2025,
                'variable_cost': variable_2025,
                'profit': profit_2025,
                'revenue_growth': rev_growth_2025,
                'profit_growth': (profit_2025 - base_profit) / base_profit if base_profit > 0 else 0
            },
            '2026': {
                'revenue': revenue_2026,
                'fixed_cost': fixed_2026,
                'variable_cost': variable_2026,
                'profit': profit_2026,
                'revenue_growth': rev_growth_2026,
                'profit_growth': (profit_2026 - profit_2025) / profit_2025 if profit_2025 > 0 else 0
            },
            'cost_structure': {
                'fixed_cost_ratio': fixed_2026 / revenue_2026 if revenue_2026 > 0 else 0,
                'variable_cost_ratio': variable_2026 / revenue_2026 if revenue_2026 > 0 else 0,
                'net_margin': profit_2026 / revenue_2026 if revenue_2026 > 0 else 0
            }
        }


# ============ 使用示例 ============
if __name__ == "__main__":
    print("=" * 70)
    print("光库科技 - 收入-成本模型预测")
    print("=" * 70)
    
    forecaster = RevenueCostForecaster()
    
    # 添加光通信行业标杆
    # 注意：这里需要真实的Tushare Token才能获取数据
    # 以下为演示逻辑，实际运行需要配置Tushare
    
    print("\n加载行业标杆...")
    forecaster.add_benchmark("300394.SZ", "天孚通信")
    forecaster.add_benchmark("300308.SZ", "中际旭创")
    forecaster.add_benchmark("300502.SZ", "新易盛")
    
    # 如果没有获取到数据，使用模拟数据演示
    if not forecaster.benchmark_data:
        print("\n注意: 未获取到真实数据，使用模拟数据演示逻辑...")
        # 创建模拟的标杆数据
        from financial_data_fetcher import FinancialData
        import datetime
        
        # 模拟天孚通信数据
        mock_data = [
            FinancialData("300394.SZ", "天孚通信", "2024Q1", 6.5, 4.2, 2.3, 0.8, 1.5, 2.0, 1.5, 1.2, 2.7, 0.35, 0.23, 0.31, datetime.datetime.now().strftime("%Y-%m-%d"), "模拟"),
            FinancialData("300394.SZ", "天孚通信", "2024Q2", 7.2, 4.5, 2.7, 0.9, 1.8, 2.5, 1.6, 1.2, 3.0, 0.38, 0.25, 0.35, datetime.datetime.now().strftime("%Y-%m-%d"), "模拟"),
            FinancialData("300394.SZ", "天孚通信", "2024Q3", 8.1, 5.0, 3.1, 1.0, 2.1, 2.9, 1.8, 1.3, 3.3, 0.38, 0.26, 0.36, datetime.datetime.now().strftime("%Y-%m-%d"), "模拟"),
            FinancialData("300394.SZ", "天孚通信", "2024Q4", 9.0, 5.5, 3.5, 1.1, 2.4, 3.3, 2.0, 1.4, 3.6, 0.39, 0.27, 0.37, datetime.datetime.now().strftime("%Y-%m-%d"), "模拟"),
        ]
        forecaster.benchmark_data["300394.SZ"] = mock_data
    
    # 设置目标企业（光库科技）
    from financial_data_fetcher import FinancialData
    import datetime
    
    target_base = FinancialData(
        stock_code="300620.SZ",
        stock_name="光库科技",
        period="2024年报",
        revenue=8.5,
        operating_cost=7.0,
        gross_profit=1.5,
        operating_expenses=0.5,
        operating_profit=1.0,
        net_profit=1.0,
        fixed_cost=1.3,  # 估算
        variable_cost=5.7,  # 估算
        gross_margin=0.176,
        operating_margin=0.118,
        net_margin=0.118,
        fetch_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_source="年报"
    )
    
    forecaster.set_target("300620.SZ", "光库科技", target_base)
    
    # 执行预测
    result = forecaster.forecast_2025_2026(market_share_change=0)
    
    print("\n" + "=" * 70)
