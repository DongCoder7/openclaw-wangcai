#!/root/.openclaw/workspace/venv/bin/python3
"""
财务数据增强分析模块
提供完整的同比环比分析、趋势分析功能
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace')

from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd


class FinancialAnalyzer:
    """财务数据增强分析器"""
    
    def __init__(self, tushare_api=None):
        self.ts_api = tushare_api
        if not self.ts_api:
            from tushare_api import get_tushare_api
            self.ts_api = get_tushare_api()
    
    def get_complete_financial_analysis(self, ts_code: str) -> Dict:
        """
        获取完整财务分析（含同比环比）
        
        Returns:
            包含完整财务数据的字典
        """
        result = {
            'quarterly_data': [],
            'yearly_data': [],
            'yoy_analysis': [],
            'qoq_analysis': [],
            'profitability_trend': [],
            'latest_fina': None,
            'risk_alerts': []
        }
        
        # 1. 获取季度利润表
        income = self.ts_api.get_income(ts_code)
        if income is not None and not income.empty:
            result['quarterly_data'] = income.head(8).to_dict('records')
        
        # 2. 获取年度数据
        try:
            import tushare as ts
            ts.set_token(self.ts_api.token)
            pro = ts.pro_api()
            yearly = pro.income(ts_code=ts_code, period="20241231")
            if yearly is not None and not yearly.empty:
                result['yearly_data'] = yearly.head(5).to_dict('records')
        except:
            pass
        
        # 3. 获取财务指标
        fina = self.ts_api.get_fina_indicator(ts_code)
        if fina is not None and not fina.empty:
            result['profitability_trend'] = fina.head(8).to_dict('records')
            result['latest_fina'] = fina.iloc[0].to_dict() if len(fina) > 0 else None
        
        # 4. 计算同比环比
        if result['quarterly_data']:
            result['yoy_analysis'] = self._calculate_yoy(result['quarterly_data'])
            result['qoq_analysis'] = self._calculate_qoq(result['quarterly_data'])
        
        # 5. 风险警示
        result['risk_alerts'] = self._generate_risk_alerts(result)
        
        return result
    
    def _calculate_yoy(self, quarterly_data: List[Dict]) -> List[Dict]:
        """计算同比数据（与去年同期对比）"""
        yoy_results = []
        
        df = pd.DataFrame(quarterly_data)
        if 'end_date' not in df.columns:
            return yoy_results
        
        df = df.sort_values('end_date', ascending=False)
        
        for i in range(len(df)):
            curr = df.iloc[i]
            curr_date = str(curr['end_date'])
            
            # 找去年同期（往前推4个季度）
            if i + 4 < len(df):
                prev = df.iloc[i + 4]
                
                # 收入同比
                curr_revenue = curr.get('total_revenue', 0)
                prev_revenue = prev.get('total_revenue', 0)
                yoy_revenue = ((curr_revenue - prev_revenue) / abs(prev_revenue) * 100) if prev_revenue else 0
                
                # 净利润同比
                curr_profit = curr.get('n_income_attr_p', 0)
                prev_profit = prev.get('n_income_attr_p', 0)
                yoy_profit = ((curr_profit - prev_profit) / abs(prev_profit) * 100) if prev_profit else 0
                
                yoy_results.append({
                    'period': curr_date,
                    'revenue_yoy': round(yoy_revenue, 2),
                    'profit_yoy': round(yoy_profit, 2),
                    'revenue': curr_revenue,
                    'profit': curr_profit
                })
        
        return yoy_results
    
    def _calculate_qoq(self, quarterly_data: List[Dict]) -> List[Dict]:
        """计算环比数据（与上季度对比）"""
        qoq_results = []
        
        df = pd.DataFrame(quarterly_data)
        if 'end_date' not in df.columns:
            return qoq_results
        
        df = df.sort_values('end_date', ascending=False)
        
        for i in range(len(df) - 1):
            curr = df.iloc[i]
            prev = df.iloc[i + 1]
            
            curr_date = str(curr['end_date'])
            
            # 收入环比
            curr_revenue = curr.get('total_revenue', 0)
            prev_revenue = prev.get('total_revenue', 0)
            qoq_revenue = ((curr_revenue - prev_revenue) / abs(prev_revenue) * 100) if prev_revenue else 0
            
            # 净利润环比
            curr_profit = curr.get('n_income_attr_p', 0)
            prev_profit = prev.get('n_income_attr_p', 0)
            qoq_profit = ((curr_profit - prev_profit) / abs(prev_profit) * 100) if prev_profit else 0
            
            qoq_results.append({
                'period': curr_date,
                'revenue_qoq': round(qoq_revenue, 2),
                'profit_qoq': round(qoq_profit, 2),
                'revenue': curr_revenue,
                'profit': curr_profit
            })
        
        return qoq_results
    
    def _generate_risk_alerts(self, data: Dict) -> List[str]:
        """生成风险警示"""
        alerts = []
        
        # 检查同比下滑
        yoy = data.get('yoy_analysis', [])
        if yoy:
            decline_count = sum(1 for x in yoy if x.get('profit_yoy', 0) < -10)
            if decline_count >= 2:
                alerts.append(f"🔴 业绩风险：连续{decline_count}个季度净利润同比下滑超10%")
            
            latest = yoy[0] if yoy else {}
            if latest.get('profit_yoy', 0) < -20:
                alerts.append(f"🔴 盈利恶化：最新季度净利润同比{latest['profit_yoy']:+.1f}%")
        
        # 检查ROE趋势
        fina = data.get('profitability_trend', [])
        if fina and len(fina) >= 2:
            latest_roe = fina[0].get('roe', 0)
            prev_roe = fina[1].get('roe', 0)
            if latest_roe and prev_roe and latest_roe < prev_roe * 0.8:
                alerts.append(f"🟡 ROE下滑：从{prev_roe:.2f}%降至{latest_roe:.2f}%")
        
        return alerts
    
    def format_financial_section(self, data: Dict) -> str:
        """
        格式化财务分析章节（Markdown格式）
        
        Returns:
            完整财务分析Markdown文本
        """
        lines = [
            "## 五、财务深度分析",
            "",
            "### 5.1 最近8个季度业绩数据",
            "",
            "| 季度 | 营业收入(万元) | 归母净利润(万元) |",
            "|:-----|:---------------|:-----------------|",
        ]
        
        # 季度数据
        for item in data.get('quarterly_data', [])[:8]:
            period = item.get('end_date', '')
            revenue = item.get('total_revenue', 0)
            profit = item.get('n_income_attr_p', 0)
            lines.append(f"| {period} | {revenue:,.0f} | {profit:,.0f} |")
        
        # 同比分析
        lines.extend([
            "",
            "### 5.2 季度同比分析（YoY）",
            "",
            "| 季度 | 收入同比 | 净利润同比 | 评价 |",
            "|:-----|:---------|:-----------|:-----|",
        ])
        
        for item in data.get('yoy_analysis', []):
            period = item.get('period', '')
            rev_yoy = item.get('revenue_yoy', 0)
            profit_yoy = item.get('profit_yoy', 0)
            
            # 评价
            if profit_yoy > 20:
                eval_mark = "🟢 高增长"
            elif profit_yoy > 0:
                eval_mark = "🟡 增长"
            elif profit_yoy > -20:
                eval_mark = "🟠 下滑"
            else:
                eval_mark = "🔴 大幅下滑"
            
            lines.append(f"| {period} | {rev_yoy:+.1f}% | {profit_yoy:+.1f}% | {eval_mark} |")
        
        # 环比分析
        lines.extend([
            "",
            "### 5.3 季度环比分析（QoQ）",
            "",
            "| 季度 | 收入环比 | 净利润环比 | 评价 |",
            "|:-----|:---------|:-----------|:-----|",
        ])
        
        for item in data.get('qoq_analysis', []):
            period = item.get('period', '')
            rev_qoq = item.get('revenue_qoq', 0)
            profit_qoq = item.get('profit_qoq', 0)
            
            if rev_qoq > 50:
                eval_mark = "🟢 大幅增长"
            elif rev_qoq > 0:
                eval_mark = "🟡 增长"
            elif rev_qoq > -30:
                eval_mark = "🟠 下滑"
            else:
                eval_mark = "🔴 大幅下滑"
            
            lines.append(f"| {period} | {rev_qoq:+.1f}% | {profit_qoq:+.1f}% | {eval_mark} |")
        
        # 盈利能力趋势
        lines.extend([
            "",
            "### 5.4 盈利能力趋势",
            "",
            "| 季度 | ROE(%) | 毛利率(%) | 净利率(%) | 资产负债率(%) |",
            "|:-----|:-------|:----------|:----------|:--------------|",
        ])
        
        for item in data.get('profitability_trend', [])[:8]:
            period = item.get('end_date', '')
            roe = item.get('roe', 0)
            gross = item.get('grossprofit_margin', 0)
            net = item.get('netprofit_margin', 0)
            debt = item.get('debt_to_assets', 0)
            lines.append(f"| {period} | {roe:.2f} | {gross:.2f} | {net:.2f} | {debt:.2f} |")
        
        # 杜邦分析
        latest = data.get('latest_fina', {})
        if latest:
            roe = latest.get('roe', 0)
            net_margin = latest.get('netprofit_margin', 0)
            # 资产周转率 = ROE / (净利率 * 权益乘数) - 简化计算
            debt_ratio = latest.get('debt_to_assets', 0)
            equity_multiplier = 1 / (1 - debt_ratio/100) if debt_ratio < 100 else 1
            asset_turnover = roe / (net_margin * equity_multiplier) if (net_margin * equity_multiplier) > 0 else 0
            
            lines.extend([
                "",
                "### 5.5 杜邦分析（最新季度）",
                "",
                "```",
                f"ROE = 净利率 × 资产周转率 × 权益乘数",
                f"{roe:.2f}% = {net_margin:.2f}% × {asset_turnover:.2f} × {equity_multiplier:.2f}",
                "```",
                "",
                f"- **净利率**：{net_margin:.2f}%（盈利能力）",
                f"- **资产周转率**：{asset_turnover:.2f}（运营效率）",
                f"- **权益乘数**：{equity_multiplier:.2f}（财务杠杆）",
            ])
        
        # 风险警示
        alerts = data.get('risk_alerts', [])
        if alerts:
            lines.extend([
                "",
                "### 5.6 财务风险警示 ⚠️",
                "",
            ])
            for alert in alerts:
                lines.append(f"- {alert}")
        
        return "\n".join(lines)


# 便捷函数
def analyze_financial_data(ts_code: str) -> str:
    """
    便捷函数：获取完整财务分析
    
    Args:
        ts_code: 股票代码
        
    Returns:
        Markdown格式的财务分析
    """
    analyzer = FinancialAnalyzer()
    data = analyzer.get_complete_financial_analysis(ts_code)
    return analyzer.format_financial_section(data)


if __name__ == "__main__":
    # 测试
    print("🧪 Testing Financial Analyzer")
    print("="*60)
    
    # 测试安泰科技
    report = analyze_financial_data("000969.SZ")
    print(report[:2000])
    print("\n... [后续内容省略] ...")
    print("\n✅ Test completed!")
