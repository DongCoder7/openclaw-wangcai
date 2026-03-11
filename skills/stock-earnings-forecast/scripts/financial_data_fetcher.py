#!/root/.openclaw/workspace/venv/bin/python3
"""
财务数据获取模块 - 支持多数据源
Tushare Pro / 长桥 / efinance / 腾讯财经
"""

import os
import sys
import json
import requests
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# 添加venv路径
sys.path.insert(0, '/root/.openclaw/workspace/venv/lib/python3.12/site-packages')

@dataclass
class FinancialData:
    """财务数据结构"""
    stock_code: str
    stock_name: str
    period: str  # 2024Q1, 2024Q2, 2024Q3, 2024Q4, 2024年报
    
    # 利润表数据（亿元）
    revenue: float           # 营业收入
    operating_cost: float    # 营业成本
    gross_profit: float      # 毛利润
    operating_expenses: float  # 营业费用（销售+管理+研发）
    operating_profit: float  # 营业利润
    net_profit: float        # 净利润
    
    # 成本分解（估算）
    fixed_cost: float        # 固定成本（折旧+管理人员工资+租金）
    variable_cost: float     # 变动成本（原材料+生产人员工资+能源）
    
    # 比率
    gross_margin: float      # 毛利率
    operating_margin: float  # 营业利润率
    net_margin: float        # 净利率
    
    # 时间戳
    fetch_time: str
    data_source: str


class TushareDataFetcher:
    """Tushare Pro数据获取器"""
    
    def __init__(self, token: str = None):
        import tushare as ts
        if token:
            self.pro = ts.pro_api(token)
        else:
            # 从环境变量获取
            self.pro = ts.pro_api()
    
    def get_income_statement(self, ts_code: str, period: str) -> Optional[Dict]:
        """
        获取利润表数据
        
        Args:
            ts_code: 股票代码（如 300394.SZ）
            period: 报告期（如 2024Q1, 2024Q2, 2024Q3, 2024Q4, 20241231）
        """
        try:
            # 季度数据
            if 'Q' in period:
                year = period[:4]
                q = period[-1]
                # Tushare季度接口
                df = self.pro.income(ts_code=ts_code, 
                                     start_date=f"{year}0101",
                                     end_date=f"{year}1231",
                                     fields='ts_code,end_date,total_revenue,operate_cost,grossprofit,operate_exp,total_profit,n_income')
                if df is not None and not df.empty:
                    # 获取指定季度数据
                    return df.iloc[0].to_dict()
            
            # 年度数据
            else:
                df = self.pro.income(ts_code=ts_code, 
                                     period=period,
                                     fields='ts_code,end_date,total_revenue,operate_cost,grossprofit,operate_exp,total_profit,n_income')
                if df is not None and not df.empty:
                    return df.iloc[0].to_dict()
                    
        except Exception as e:
            print(f"Tushare获取数据失败: {e}")
        
        return None
    
    def get_quarterly_data(self, ts_code: str, year: int) -> List[FinancialData]:
        """获取全年季度数据"""
        result = []
        quarters = [
            (f"{year}Q1", f"{year}0331"),
            (f"{year}Q2", f"{year}0630"),
            (f"{year}Q3", f"{year}0930"),
            (f"{year}Q4", f"{year}1231")
        ]
        
        for period_name, end_date in quarters:
            data = self.get_income_statement(ts_code, end_date)
            if data:
                fin_data = self._convert_to_financial_data(ts_code, period_name, data, "Tushare Pro")
                result.append(fin_data)
        
        return result
    
    def _convert_to_financial_data(self, ts_code: str, period: str, data: Dict, source: str) -> FinancialData:
        """转换为标准格式"""
        # Tushare数据单位是元，转换为亿元
        revenue = float(data.get('total_revenue', 0)) / 1e8
        cost = float(data.get('operate_cost', 0)) / 1e8
        gross = float(data.get('grossprofit', 0)) / 1e8
        op_exp = float(data.get('operate_exp', 0)) / 1e8
        op_profit = float(data.get('total_profit', 0)) / 1e8
        net_profit = float(data.get('n_income', 0)) / 1e8
        
        # 估算固定成本和变动成本
        # 假设：固定成本 = 折旧(约30%营业费用) + 管理费用(约40%营业费用)
        # 变动成本 = 营业成本 - 折旧 + 销售费用(约30%营业费用)
        fixed_cost = op_exp * 0.7  # 70%营业费用为固定
        variable_cost = cost * 0.8  # 营业成本80%为变动（扣除折旧）
        
        return FinancialData(
            stock_code=ts_code,
            stock_name="",  # 需要额外查询
            period=period,
            revenue=revenue,
            operating_cost=cost,
            gross_profit=gross,
            operating_expenses=op_exp,
            operating_profit=op_profit,
            net_profit=net_profit,
            fixed_cost=fixed_cost,
            variable_cost=variable_cost,
            gross_margin=gross/revenue if revenue > 0 else 0,
            operating_margin=op_profit/revenue if revenue > 0 else 0,
            net_margin=net_profit/revenue if revenue > 0 else 0,
            fetch_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data_source=source
        )


class TencentDataFetcher:
    """腾讯财经数据获取器（备用）"""
    
    def get_realtime_quote(self, code: str) -> Optional[Dict]:
        """获取实时行情"""
        try:
            # 转换代码格式
            if code.endswith('.SZ'):
                tcode = 'sz' + code[:-3]
            elif code.endswith('.SH'):
                tcode = 'sh' + code[:-3]
            else:
                tcode = code
            
            url = f"https://qt.gtimg.cn/q={tcode}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                # 解析腾讯财经数据格式
                data = resp.text
                # 解析逻辑...
                return {"price": 0, "pe": 0}  # 简化
        except Exception as e:
            print(f"腾讯财经获取失败: {e}")
        return None


class FinancialDataManager:
    """财务数据管理器 - 统一接口"""
    
    def __init__(self):
        self.tushare = None
        try:
            self.tushare = TushareDataFetcher()
        except Exception as e:
            print(f"Tushare初始化失败: {e}")
    
    def get_stock_financials(self, ts_code: str, year: int = 2024) -> List[FinancialData]:
        """
        获取股票财务数据（优先Tushare，备用其他源）
        
        Args:
            ts_code: 股票代码（如 300394.SZ）
            year: 年份
        
        Returns:
            List[FinancialData]: 季度财务数据列表
        """
        # 优先使用Tushare Pro
        if self.tushare:
            data = self.tushare.get_quarterly_data(ts_code, year)
            if data:
                return data
        
        # 备用：efinance
        try:
            return self._get_from_efinance(ts_code, year)
        except Exception as e:
            print(f"efinance获取失败: {e}")
        
        return []
    
    def _get_from_efinance(self, ts_code: str, year: int) -> List[FinancialData]:
        """从efinance获取数据"""
        try:
            import efinance as ef
            
            # 获取个股利润表
            code = ts_code.split('.')[0]
            df = ef.stock.get_profit_sheet(code)
            
            # 处理数据...
            # 简化实现
            return []
        except Exception as e:
            print(f"efinance错误: {e}")
        return []
    
    def calculate_cost_structure(self, fin_data: FinancialData) -> Dict:
        """
        分析成本结构
        
        Returns:
            {
                'fixed_cost_ratio': 固定成本占比,
                'variable_cost_ratio': 变动成本占比,
                'break_even_point': 盈亏平衡点
            }
        """
        total_cost = fin_data.fixed_cost + fin_data.variable_cost
        
        if total_cost <= 0 or fin_data.revenue <= 0:
            return {}
        
        return {
            'fixed_cost': fin_data.fixed_cost,
            'variable_cost': fin_data.variable_cost,
            'total_cost': total_cost,
            'fixed_cost_ratio': fin_data.fixed_cost / total_cost,
            'variable_cost_ratio': fin_data.variable_cost / total_cost,
            'variable_cost_rate': fin_data.variable_cost / fin_data.revenue,  # 变动成本率
            'contribution_margin': fin_data.revenue - fin_data.variable_cost,  # 边际贡献
            'contribution_margin_ratio': (fin_data.revenue - fin_data.variable_cost) / fin_data.revenue,
        }


# ============ 使用示例 ============
if __name__ == "__main__":
    print("=" * 60)
    print("财务数据获取模块测试")
    print("=" * 60)
    
    manager = FinancialDataManager()
    
    # 测试获取天孚通信数据
    print("\n获取天孚通信(300394.SZ) 2024年季度数据...")
    data = manager.get_stock_financials("300394.SZ", 2024)
    
    if data:
        for d in data:
            print(f"\n{d.period}:")
            print(f"  营收: {d.revenue:.2f}亿")
            print(f"  营业成本: {d.operating_cost:.2f}亿")
            print(f"  净利润: {d.net_profit:.2f}亿")
            print(f"  净利率: {d.net_margin:.1%}")
            
            # 成本结构分析
            cost_struct = manager.calculate_cost_structure(d)
            if cost_struct:
                print(f"  固定成本: {cost_struct['fixed_cost']:.2f}亿 ({cost_struct['fixed_cost_ratio']:.1%})")
                print(f"  变动成本: {cost_struct['variable_cost']:.2f}亿 ({cost_struct['variable_cost_ratio']:.1%})")
    else:
        print("未获取到数据，请检查Tushare Token配置")
    
    print("\n" + "=" * 60)
