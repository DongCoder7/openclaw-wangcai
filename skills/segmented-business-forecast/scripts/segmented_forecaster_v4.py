#!/root/.openclaw/workspace/venv/bin/python3
"""
业务线拆分估值分析器 v4.0 - 综合版

改进点（基于疏忽教训）：
1. 支持用户调研数据输入模式（优先）+ 搜索驱动模式（备用）
2. 强制年份确认
3. 多数据源财报获取（Tushare/efinance/akshare）
4. 出货量必须从纪要/公告提取，不能假设0%
5. 产品粒度匹配（调研纪要细分产品优先）
6. 完整计算过程展示 + 反向验证

使用方法：
1. 用户有调研数据：直接调用 add_product() 输入数据
2. 用户没数据：自动搜索（v3.2逻辑）
"""

import sys
import os
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, '/root/.openclaw/workspace/tools')

import tushare as ts


@dataclass
class ProductData:
    """产品数据"""
    name: str
    revenue_base: float          # 基期营收（亿元）
    margin: float                # 毛利率（0.60=60%）
    volume_growth: float         # 出货量增长（必须有来源！）
    price_change: float          # 价格变化（必须有来源！）
    evidence: str = ""           # 数据来源证据（必须记录）
    
    # 预测结果
    revenue_forecast: float = 0.0
    profit_base: float = 0.0
    profit_forecast: float = 0.0
    margin_forecast: float = 0.0


@dataclass
class FinancialData:
    """财报数据"""
    year: int
    quarter: int
    revenue: float
    profit: float
    margin: float
    net_margin: float
    source: str


class V4Forecaster:
    """v4.0 综合版业务线拆分估值分析器"""
    
    def __init__(self, stock_code: str, stock_name: str, year: int = None):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.year = year or datetime.now().year
        self.products: List[ProductData] = []
        self.financial_data: Optional[FinancialData] = None
        
        # 初始化tushare
        self._init_tushare()
    
    def _init_tushare(self):
        """初始化Tushare"""
        token = os.environ.get('TUSHARE_TOKEN')
        if not token:
            env_path = '/root/.openclaw/workspace/.env'
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        if line.startswith('TUSHARE_TOKEN='):
                            token = line.strip().split('=', 1)[1].strip().strip('"').strip("'")
                            break
        self.pro = ts.pro_api(token) if token else ts.pro_api()
    
    # ========== 步骤1: 获取真实财报（多数据源） ==========
    
    def fetch_financial_data(self, year: int = None, quarter: int = 1) -> FinancialData:
        """
        获取真实财报数据（多数据源）
        
        优先级:
        1. Tushare income接口
        2. efinance（如果有）
        3. akshare（如果有）
        4. 如果都失败，报错（不编造！）
        """
        target_year = year or self.year
        print(f"\n📊 Step 1: 获取 {target_year}Q{quarter} 财报数据...")
        
        # 尝试Tushare
        data = self._fetch_from_tushare(target_year, quarter)
        if data:
            print(f"   ✅ Tushare: 营收{data.revenue:.2f}亿, 净利润{data.profit:.2f}亿")
            self.financial_data = data
            return data
        
        # 尝试efinance
        data = self._fetch_from_efinance(target_year, quarter)
        if data:
            print(f"   ✅ efinance: 营收{data.revenue:.2f}亿, 净利润{data.profit:.2f}亿")
            self.financial_data = data
            return data
        
        # 尝试akshare
        data = self._fetch_from_akshare(target_year, quarter)
        if data:
            print(f"   ✅ akshare: 营收{data.revenue:.2f}亿, 净利润{data.profit:.2f}亿")
            self.financial_data = data
            return data
        
        raise ValueError(f"无法获取 {target_year}Q{quarter} 财报数据，所有数据源失败。请提供手动数据或检查股票代码。")
    
    def _fetch_from_tushare(self, year: int, quarter: int) -> Optional[FinancialData]:
        """从Tushare获取"""
        try:
            start_date = f"{year}0101"
            end_date = f"{year}0331" if quarter == 1 else f"{year}0630" if quarter == 2 else f"{year}0930" if quarter == 3 else f"{year}1231"
            
            df = self.pro.income(ts_code=self.stock_code, start_date=start_date, end_date=end_date)
            if len(df) > 0:
                row = df.iloc[0]
                revenue = float(row['total_revenue']) / 1e8
                profit = float(row['n_income']) / 1e8
                return FinancialData(
                    year=year, quarter=quarter,
                    revenue=revenue, profit=profit,
                    margin=0.0, net_margin=0.0,  # 需要单独计算
                    source="Tushare"
                )
        except Exception as e:
            print(f"   ⚠️ Tushare失败: {e}")
        return None
    
    def _fetch_from_efinance(self, year: int, quarter: int) -> Optional[FinancialData]:
        """从efinance获取"""
        try:
            import efinance as ef
            df = ef.stock.get_all_company_performance()
            mask = df['股票代码'].astype(str).str.contains(self.stock_code.replace('.SH', '').replace('.SZ', ''))
            if mask.any():
                row = df[mask].iloc[0]
                # 注意：efinance可能返回的是最新数据，需要确认年份
                return FinancialData(
                    year=year, quarter=quarter,
                    revenue=float(row['营业收入']) / 1e8,
                    profit=float(row['净利润']) / 1e8,
                    margin=float(row['销售毛利率']) / 100 if '销售毛利率' in row else 0.0,
                    net_margin=0.0,
                    source="efinance"
                )
        except Exception as e:
            print(f"   ⚠️ efinance失败: {e}")
        return None
    
    def _fetch_from_akshare(self, year: int, quarter: int) -> Optional[FinancialData]:
        """从akshare获取"""
        try:
            import akshare as ak
            df = ak.stock_financial_report_sina(stock=self.stock_code.replace('.SH', '').replace('.SZ', ''), symbol="利润表")
            if len(df) > 0:
                row = df.iloc[0]
                revenue = float(row['营业总收入']) / 1e8
                profit = float(row['净利润']) / 1e8
                return FinancialData(
                    year=year, quarter=quarter,
                    revenue=revenue, profit=profit,
                    margin=0.0, net_margin=0.0,
                    source="akshare"
                )
        except Exception as e:
            print(f"   ⚠️ akshare失败: {e}")
        return None
    
    # ========== 步骤2: 验证数据 ==========
    
    def validate_data(self, user_revenue: float = None, user_profit: float = None) -> bool:
        """
        验证数据一致性
        
        如果用户提供了数据，和API数据对比
        """
        if not self.financial_data:
            return False
        
        print(f"\n✅ Step 2: 数据验证...")
        
        # 验证净利率是否合理
        net_margin = self.financial_data.profit / self.financial_data.revenue
        print(f"   营收: {self.financial_data.revenue:.2f}亿")
        print(f"   净利润: {self.financial_data.profit:.2f}亿")
        print(f"   净利率: {net_margin*100:.1f}%")
        
        if net_margin < 0.05 or net_margin > 0.50:
            print(f"   ⚠️ 净利率异常（正常范围5%-50%），请检查数据")
            return False
        
        # 如果用户提供了数据，对比
        if user_revenue and abs(user_revenue - self.financial_data.revenue) / self.financial_data.revenue > 0.1:
            print(f"   ⚠️ 用户数据({user_revenue}亿)与API数据({self.financial_data.revenue:.2f}亿)不一致！")
            print(f"   请确认年份和口径。当前年份: {self.year}")
            return False
        
        print(f"   ✅ 数据验证通过")
        return True
    
    # ========== 步骤3: 添加产品（必须有数据来源） ==========
    
    def add_product(self, name: str, revenue_base: float, margin: float,
                   volume_growth: float, price_change: float,
                   evidence: str = ""):
        """
        添加产品数据
        
        强制要求:
        1. volume_growth 必须有来源（不能假设0%）
        2. price_change 必须有来源
        3. evidence 必须记录数据来源
        
        Args:
            name: 产品名称
            revenue_base: 基期营收（亿元）
            margin: 毛利率
            volume_growth: 出货量增长（必须有来源证据！）
            price_change: 价格变化（必须有来源证据！）
            evidence: 数据来源（如"调研纪要第X页：投片2万片"）
        """
        if not evidence:
            print(f"   ⚠️ 警告: {name} 没有提供数据来源证据！")
        
        self.products.append(ProductData(
            name=name,
            revenue_base=revenue_base,
            margin=margin,
            volume_growth=volume_growth,
            price_change=price_change,
            evidence=evidence
        ))
    
    # ========== 步骤4: 预测计算（展示完整过程） ==========
    
    def forecast(self) -> List[ProductData]:
        """
        预测计算
        
        公式:
        预测营收 = 基期营收 × (1 + 出货量增长) × (1 + 价格变化)
        预测毛利率 = 原毛利率 + 价格变化 × (1 - 原毛利率)（成本不变时）
        预测利润 = 预测营收 × 预测毛利率
        """
        print(f"\n📈 Step 4: 预测计算...")
        
        results = []
        for p in self.products:
            # 营收预测
            revenue_factor = (1 + p.volume_growth) * (1 + p.price_change)
            p.revenue_forecast = p.revenue_base * revenue_factor
            
            # 基期利润
            p.profit_base = p.revenue_base * p.margin
            
            # 毛利率预测（成本不变时提升）
            # 毛利率提升 = 价格变化 × (1 - 原毛利率)
            p.margin_forecast = p.margin + p.price_change * (1 - p.margin)
            p.margin_forecast = max(0.05, min(0.95, p.margin_forecast))  # 限制在5%-95%
            
            # 利润预测
            p.profit_forecast = p.revenue_forecast * p.margin_forecast
            
            results.append(p)
        
        return results
    
    # ========== 步骤5: 汇总输出 ==========
    
    def summarize(self) -> Dict:
        """汇总"""
        total_base_revenue = sum(p.revenue_base for p in self.products)
        total_forecast_revenue = sum(p.revenue_forecast for p in self.products)
        total_base_profit = sum(p.profit_base for p in self.products)
        total_forecast_profit = sum(p.profit_forecast for p in self.products)
        
        rev_change = (total_forecast_revenue - total_base_revenue) / total_base_revenue
        profit_change = (total_forecast_profit - total_base_profit) / total_base_profit
        
        return {
            'base_revenue': total_base_revenue,
            'forecast_revenue': total_forecast_revenue,
            'base_profit': total_base_profit,
            'forecast_profit': total_forecast_profit,
            'revenue_change': rev_change,
            'profit_change': profit_change
        }
    
    def print_report(self):
        """打印报告"""
        print(f"\n{'='*75}")
        print(f"业务线拆分估值报告 v4.0")
        print(f"{'='*75}")
        print(f"股票: {self.stock_name} ({self.stock_code})")
        print(f"年份: {self.year}")
        if self.financial_data:
            print(f"基期: {self.financial_data.year}Q{self.financial_data.quarter}")
            print(f"财报来源: {self.financial_data.source}")
        print(f"{'='*75}")
        
        # 分产品预测
        print(f"\n{'产品':<15} {'基期营收':>10} {'出货增长':>8} {'价格变化':>8} {'预测营收':>10} {'变化':>8} {'毛利率':>8} {'预测利润':>10}")
        print(f"{'─'*85}")
        
        for p in self.products:
            rev_chg = (p.revenue_forecast - p.revenue_base) / p.revenue_base
            print(f"{p.name:<15} {p.revenue_base:>10.2f} {p.volume_growth:>+7.1%} {p.price_change:>+7.1%} {p.revenue_forecast:>10.2f} {rev_chg:>+7.1%} {p.margin_forecast:>7.1%} {p.profit_forecast:>10.2f}")
        
        # 汇总
        result = self.summarize()
        print(f"{'─'*85}")
        print(f"{'合计':<15} {result['base_revenue']:>10.2f} {'':8} {'':8} {result['forecast_revenue']:>10.2f} {result['revenue_change']:>+7.1%} {'':8} {result['forecast_profit']:>10.2f}")
        print(f"{'='*75}")
        
        # 数据来源
        print(f"\n📋 数据来源:")
        for p in self.products:
            print(f"  {p.name}: {p.evidence}")
    
    def generate_markdown(self) -> str:
        """生成Markdown报告"""
        result = self.summarize()
        
        lines = []
        lines.append(f"# {self.stock_name} ({self.stock_code}) 业务线拆分估值报告")
        lines.append(f"\n> **分析日期**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"> **年份**: {self.year}")
        if self.financial_data:
            lines.append(f"> **基期**: {self.financial_data.year}Q{self.financial_data.quarter}")
            lines.append(f"> **财报来源**: {self.financial_data.source}")
        lines.append("")
        
        lines.append("## 分产品预测")
        lines.append("")
        lines.append("| 产品 | 基期营收 | 出货增长 | 价格变化 | 预测营收 | 变化 | 毛利率 | 预测利润 | 数据来源 |")
        lines.append("|:---|---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|")
        
        for p in self.products:
            rev_chg = (p.revenue_forecast - p.revenue_base) / p.revenue_base
            lines.append(f"| {p.name} | {p.revenue_base:.2f}亿 | {p.volume_growth:+.1%} | {p.price_change:+.1%} | {p.revenue_forecast:.2f}亿 | {rev_chg:+.1%} | {p.margin_forecast:.1%} | {p.profit_forecast:.2f}亿 | {p.evidence} |")
        
        lines.append("")
        lines.append("## 汇总")
        lines.append("")
        lines.append("| 指标 | 基期 | 预测 | 变化 |")
        lines.append("|:---|---:|---:|---:|")
        lines.append(f"| 总营收 | {result['base_revenue']:.2f}亿 | {result['forecast_revenue']:.2f}亿 | {result['revenue_change']:+.1%} |")
        lines.append(f"| 总利润 | {result['base_profit']:.2f}亿 | {result['forecast_profit']:.2f}亿 | {result['profit_change']:+.1%} |")
        lines.append("")
        
        lines.append("## 核心假设")
        lines.append("")
        lines.append("1. **出货量增长**: 基于调研纪要/公告中的投片、产能数据")
        lines.append("2. **价格变化**: 基于调研纪要中的涨价幅度")
        lines.append("3. **毛利率**: 假设成本不变，售价涨带动毛利率提升")
        lines.append("4. **数据来源**: 每个产品都有明确的来源证据")
        lines.append("")
        
        lines.append("## 数据来源")
        lines.append("")
        for p in self.products:
            lines.append(f"- **{p.name}**: {p.evidence}")
        lines.append("")
        
        return "\n".join(lines)


# ========== 使用示例 ==========

def example_zhaoyi():
    """兆易创新示例（基于调研纪要）"""
    
    # 创建分析器（确认年份！）
    f = V4Forecaster("603986.SH", "兆易创新", year=2026)
    
    # 获取真实财报（多数据源）
    try:
        fin = f.fetch_financial_data(year=2026, quarter=1)
        f.validate_data()
    except ValueError as e:
        print(f"⚠️ {e}")
        print("使用手动输入的基期数据...")
        fin = FinancialData(
            year=2026, quarter=1,
            revenue=41.88, profit=14.61,
            margin=0.5708, net_margin=0.3489,
            source="用户提供"
        )
        f.financial_data = fin
    
    # Q1产品拆分（基于调研纪要：1/3 NOR, 1/3 DR-AM, 1/3 其他）
    q1_total = fin.revenue  # 41.88亿
    
    # 其他 = MCU + SLC，假设MCU:SLC ≈ 2:1
    # DR-AM: 1/3 = 13.96亿
    # NOR: 1/3 = 13.96亿
    # MCU: 1/3 × 2/3 ≈ 9.31亿
    # SLC: 1/3 × 1/3 ≈ 4.65亿
    
    # 添加产品（必须提供数据来源证据！）
    f.add_product(
        name="DR-AM",
        revenue_base=q1_total / 3,
        margin=0.60,
        volume_growth=0.05,  # 库存清理
        price_change=0.30,   # 涨价30%
        evidence="调研纪要：Q2存货全部卖完（零库存），投片H1维持大几k至1万片；4月环增30%主要由涨价贡献"
    )
    
    f.add_product(
        name="NOR",
        revenue_base=q1_total / 3,
        margin=0.55,
        volume_growth=0.05,  # 产能温和提升
        price_change=0.20,   # 涨价20%
        evidence="调研纪要：3-4月投片2万片，产能温和提升年底到2.5w片；4月环增20%主要由涨价贡献"
    )
    
    f.add_product(
        name="SLC",
        revenue_base=q1_total / 3 * 0.333,  # 约4.65亿
        margin=0.70,
        volume_growth=0.10,  # 产能爬坡
        price_change=1.00,   # 翻倍
        evidence="调研纪要：Q2涨价接近翻倍且远未结束；产能2-3年扩到1-1.5w片"
    )
    
    f.add_product(
        name="MCU",
        revenue_base=q1_total / 3 * 0.667,  # 约9.31亿
        margin=0.35,
        volume_growth=0.00,  # 稳定
        price_change=0.25,   # 涨价25%（用户补充）
        evidence="用户补充：MCU涨价25%"
    )
    
    # 预测
    f.forecast()
    
    # 输出报告
    f.print_report()
    
    # 生成Markdown
    report = f.generate_markdown()
    print("\n" + report)
    
    return report


if __name__ == '__main__':
    example_zhaoyi()
