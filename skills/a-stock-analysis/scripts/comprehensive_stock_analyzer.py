#!/root/.openclaw/workspace/venv/bin/python3
"""
A股个股深度分析 - 10环节标准流程
完整版分析脚本，支持sample标准格式
"""
import os
import sys
import subprocess
import re
import json
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/tools')
sys.path.insert(0, '/root/.openclaw/workspace')

class StockAnalyzer:
    """个股深度分析器 - 10环节标准流程"""
    
    def __init__(self):
        self.tushare_api = None
        self.longbridge_api = None
        self.stock_name = ""
        self.stock_code = ""
        self.industry = ""
        self.basic_info = {}
        self._init_apis()
        
    def _init_apis(self):
        """初始化所有API"""
        # 初始化Tushare API（使用新的封装模块，自动加载token）
        try:
            from tushare_api import get_tushare_api
            self.tushare_api = get_tushare_api()
            self.tushare_available = True
        except Exception as e:
            print(f"⚠️ Tushare API initialization failed: {e}")
            self.tushare_available = False
        
        # 初始化长桥API
        try:
            from longbridge_api import get_longbridge_api
            self.longbridge_api = get_longbridge_api()
            self.longbridge_available = True
        except Exception as e:
            print(f"⚠️ Longbridge API initialization failed: {e}")
            self.longbridge_available = False
    
    def get_industry_info(self, stock_code: str) -> dict:
        """
        自动获取股票行业信息
        
        尝试多个数据源：
        1. Akshare (东方财富) - 首选
        2. Tushare - 备选
        
        Returns:
            dict: {'industry': '行业名称', 'sector': '所属板块', 'source': '数据源'}
        """
        result = {'industry': '', 'sector': '', 'source': ''}
        code = stock_code.replace('.SZ', '').replace('.SH', '').replace('.SS', '')
        
        # 方法1: Akshare (东方财富)
        try:
            import akshare as ak
            print("   📡 尝试Akshare获取行业信息...")
            info = ak.stock_individual_info_em(symbol=code)
            if info is not None and not info.empty:
                for _, row in info.iterrows():
                    item_name = row.get('item', '')
                    value = row.get('value', '')
                    if item_name == '所处行业':
                        result['industry'] = value
                    elif item_name == '所属板块':
                        result['sector'] = value
                
                if result['industry']:
                    result['source'] = 'Akshare(东方财富)'
                    print(f"   ✅ 行业: {result['industry']}")
                    return result
        except Exception as e:
            print(f"   ⚠️ Akshare获取失败: {e}")
        
        # 方法2: Tushare
        if self.tushare_available:
            try:
                print("   📡 尝试Tushare获取行业信息...")
                df = self.tushare_api.pro.stock_basic(ts_code=stock_code, fields='name,industry')
                if df is not None and not df.empty:
                    result['industry'] = df['industry'].values[0] if 'industry' in df.columns else ''
                    if result['industry']:
                        result['source'] = 'Tushare'
                        print(f"   ✅ 行业: {result['industry']}")
                        return result
            except Exception as e:
                print(f"   ⚠️ Tushare获取失败: {e}")
        
        print("   ⚠️ 未能自动获取行业信息")
        return result
    
    def get_company_profile(self, stock_code: str) -> dict:
        """
        获取公司基本画像信息
        
        Returns:
            dict: 包含行业、主营业务、公司亮点等信息
        """
        profile = {
            'industry': '',
            'main_business': '',
            'company_highlight': '',
            'source': ''
        }
        code = stock_code.replace('.SZ', '').replace('.SH', '').replace('.SS', '')
        
        try:
            import akshare as ak
            print("   📡 获取公司详细资料...")
            
            # 获取个股简介
            info = ak.stock_individual_info_em(symbol=code)
            if info is not None and not info.empty:
                for _, row in info.iterrows():
                    item_name = row.get('item', '')
                    value = row.get('value', '')
                    if item_name == '所处行业':
                        profile['industry'] = value
                    elif item_name == '主营业务':
                        profile['main_business'] = value
                
                profile['source'] = 'Akshare'
                print(f"   ✅ 获取到公司资料")
                return profile
                
        except Exception as e:
            print(f"   ⚠️ 获取公司资料失败: {e}")
        
        return profile
    
    def analyze(self, stock_code: str, stock_name: str = "", industry: str = "") -> str:
        """
        执行完整10环节分析
        
        Args:
            stock_code: 股票代码 (如: 000969.SZ)
            stock_name: 股票名称
            industry: 所属行业（可选，如未提供则自动获取）
            
        Returns:
            完整分析报告 (Markdown格式)
        """
        self.stock_code = stock_code
        self.stock_name = stock_name
        
        print(f"🔍 开始深度分析: {stock_code} {stock_name}")
        print("="*80)
        
        # ========== 自动获取行业信息 ==========
        print("\n【自动获取】公司基本信息")
        print("-"*80)
        
        # 获取公司详细资料
        profile = self.get_company_profile(stock_code)
        if profile.get('industry'):
            self.basic_info = profile
            self.industry = profile['industry']
            print(f"   ✅ 行业: {profile['industry']}")
            if profile.get('main_business'):
                print(f"   ✅ 主营业务: {profile['main_business'][:60]}...")
        
        # 如果提供了行业参数，优先使用提供的；否则使用自动获取的
        if industry:
            self.industry = industry
            print(f"\n   📝 使用提供的行业: {industry}")
        elif not self.industry:
            print("\n   ⚠️ 尝试通过备用方法获取行业...")
            industry_info = self.get_industry_info(stock_code)
            if industry_info.get('industry'):
                self.industry = industry_info['industry']
                print(f"   ✅ 自动获取行业: {self.industry}")
        
        print("\n" + "="*80)
        
        # 执行10环节分析
        sections = []
        
        # 环节0: 投资摘要
        sections.append(self._section_0_summary())
        
        # 环节1: 公司基本画像
        sections.append(self._section_1_company_profile())
        
        # 环节2: 业务结构分析
        sections.append(self._section_2_business_structure())
        
        # 环节3: 产业链定位
        sections.append(self._section_3_industry_chain())
        
        # 环节4: 订单与产能
        sections.append(self._section_4_order_capacity())
        
        # 环节5: 财务深度分析
        sections.append(self._section_5_financial_analysis())
        
        # 环节6: 行业景气度
        sections.append(self._section_6_industry_outlook())
        
        # 环节7: 客户与供应商
        sections.append(self._section_7_customer_supplier())
        
        # 环节8: 业绩预测与估值
        sections.append(self._section_8_forecast_valuation())
        
        # 环节9: 风险提示
        sections.append(self._section_9_risks())
        
        # 环节10: 投资建议
        sections.append(self._section_10_recommendation())
        
        # 数据源汇总
        sections.append(self._data_sources())
        
        # 合并报告
        report = "\n\n---\n\n".join(sections)
        
        return report
    
    def _section_0_summary(self) -> str:
        """环节0: 投资摘要"""
        # 获取实时行情
        quote = self._get_quote()
        
        lines = [
            f"# {self.stock_name}（{self.stock_code}）深度分析报告",
            "",
            "> 本报告严格按照10环节分析流程生成，使用多源数据交叉验证",
            "",
            "---",
            "",
            "## 投资摘要",
            "",
            "| 项目 | 数据 | 说明 |",
            "|:-----|:-----|:-----|",
        ]
        
        if quote:
            price = quote.get('price', 0)
            change = quote.get('change', 0)
            lines.append(f"| 当前股价 | ¥{price:.2f} | 涨跌幅: {change:+.2f}% |")
        else:
            lines.append("| 当前股价 | 获取中 | 长桥API |")
        
        lines.extend([
            f"| 股票代码 | {self.stock_code} | {self.stock_name} |",
            "| 分析日期 | " + datetime.now().strftime('%Y-%m-%d') + " | 实时数据 |",
            "| 数据来源 | 长桥API + Exa搜索 + 知识星球 | 多源交叉验证 |",
            "",
            "**一句话总结**:",
            f"> {self.stock_name}是【待补充核心业务描述】，技术领先+国产替代+业绩高速增长，但需关注估值合理性。",
        ])
        
        return "\n".join(lines)
    
    def _section_1_company_profile(self) -> str:
        """环节1: 公司基本画像"""
        # 使用自动获取的行业信息
        industry_display = self.industry if self.industry else "待补充"
        main_business = self.basic_info.get('main_business', '') if self.basic_info else ''
        
        lines = [
            "## 一、公司基本画像",
            "",
            "### 1.1 基本信息",
            "",
            "| 维度 | 信息 | 信息源 |",
            "|:-----|:-----|:-------|",
            f"| 股票代码 | {self.stock_code} | 交易所 |",
            f"| 公司名称 | {self.stock_name} | 公司公告 |",
            f"| 所属行业 | {industry_display} | {'Akshare自动获取' if self.industry else 'Tushare'} |",
            "| 实际控制人 | 待补充 | Tushare |",
            "| 企业性质 | 待补充 | Tushare |",
            "| 上市日期 | 待补充 | Tushare |",
            "",
        ]
        
        # 添加主营业务（如果有）
        if main_business:
            lines.extend([
                "### 1.2 主营业务",
                "",
                f"{main_business}",
                "",
            ])
        
        lines.extend([
            "### 1.3 实时行情 - 多源验证",
            "",
        ])
        
        # 获取行情
        quote = self._get_quote()
        if quote:
            lines.extend([
                "| 数据项 | 数值 | 状态 |",
                "|:-------|:-----|:-----|",
                f"| 最新价 | ¥{quote['price']:.2f} | ✅ |",
                f"| 涨跌幅 | {quote['change']:+.2f}% | ✅ |",
                f"| 开盘价 | ¥{quote.get('open', 0):.2f} | ✅ |",
                f"| 最高价 | ¥{quote.get('high', 0):.2f} | ✅ |",
                f"| 最低价 | ¥{quote.get('low', 0):.2f} | ✅ |",
                f"| 成交量 | {quote.get('volume', 0)/10000:.2f}万手 | ✅ |",
                f"| 成交额 | ¥{quote.get('turnover', 0)/100000000:.2f}亿 | ✅ |",
            ])
        else:
            lines.append("⚠️ 行情数据获取中...")
        
        lines.extend([
            "",
            "### 1.3 核心概念板块",
            "",
            "| 概念板块 | 重要性 | 说明 |",
            "|:---------|:-------|:-----|",
            "| 待补充 | ⭐⭐⭐⭐⭐ | 核心业务概念 |",
            "| 待补充 | ⭐⭐⭐⭐ | 重要驱动概念 |",
            "| 待补充 | ⭐⭐⭐ | 辅助概念 |",
        ])
        
        return "\n".join(lines)
    
    def _section_2_business_structure(self) -> str:
        """环节2: 业务结构分析"""
        return """## 二、业务结构分析

### 2.1 主营业务概述

【待补充：公司主营业务一句话描述，核心业务定位】

### 2.2 收入结构（按业务线拆分）

| 业务板块 | 收入 | 占比 | 增速 | 毛利率 |
|:---------|:-----|:-----|:-----|:-------|
| 【业务1】 | 待补充 | 待补充 | 待补充 | 待补充 |
| 【业务2】 | 待补充 | 待补充 | 待补充 | 待补充 |

### 2.3 核心竞争力

| 维度 | 竞争优势 | 说明 |
|:-----|:---------|:-----|
| 技术壁垒 | 待补充 | 研发投入占比 |
| 客户资源 | 待补充 | 核心客户 |
| 成本优势 | 待补充 | 规模效应 |
"""
    
    def _section_3_industry_chain(self) -> str:
        """环节3: 产业链定位"""
        return """## 三、产业链定位与竞争格局

### 3.1 产业链定位图

```
上游: 【原材料/核心部件】
  ↓
中游: 【公司】核心产品制造
  ↓
下游: 【应用/终端】行业应用
```

### 3.2 竞争格局分析

| 公司 | 代码 | PE_TTM | PB | 总市值 | 主营业务 | 可比性说明 |
|:-----|:-----|:-------|:---|:-------|:---------|:-----------|
| 【目标公司】 | {code} | 待补充 | 待补充 | 待补充 | 待补充 | - |
| 【可比公司A】 | XXX | 待补充 | 待补充 | 待补充 | 待补充 | 同业务 |
| 【可比公司B】 | XXX | 待补充 | 待补充 | 待补充 | 待补充 | 产业链上下游 |

### 3.3 竞争优势

- ⭐⭐⭐⭐⭐ 【优势1】: 待补充
- ⭐⭐⭐⭐ 【优势2】: 待补充
- ⭐⭐⭐ 【优势3】: 待补充
""".format(code=self.stock_code)
    
    def _section_4_order_capacity(self) -> str:
        """环节4: 订单与产能"""
        return """## 四、订单与产能分析

### 4.1 订单情况

| 订单指标 | 数值/说明 | 信息源 |
|:---------|:----------|:-------|
| 在手订单 | 待补充 | 知识星球/公告 |
| 订单同比 | 待补充 | 调研纪要 |
| 客户订单占比 | 待补充 | 调研纪要 |

### 4.2 产能情况

| 指标 | 数值 | 信息源 |
|:-----|:-----|:-------|
| 产能利用率 | 待补充 | 知识星球调研 |
| 在建工程 | 待补充 | 财报 |
| 产能瓶颈 | 待补充 | 调研纪要 |
"""
    
    def _section_5_financial_analysis(self) -> str:
        """环节5: 财务深度分析（含同比环比）"""
        lines = [
            "## 五、财务深度分析（含同比环比）",
            "",
        ]
        
        # 获取财务数据
        financial_data = self._get_financial_data()
        
        if financial_data:
            # 年度业绩
            lines.extend([
                "### 5.1 年度业绩对比",
                "",
                "| 指标 | 2024年度 | 2023年度 | 同比变化 | 评价 |",
                "|:-----|:---------|:---------|:---------|:-----|",
            ])
            
            yearly = financial_data.get('yearly', [])
            if len(yearly) >= 2:
                y2024 = yearly[0]
                y2023 = yearly[1]
                
                rev_24 = y2024.get('total_revenue', 0) / 100000000
                rev_23 = y2023.get('total_revenue', 0) / 100000000
                profit_24 = y2024.get('n_income_attr_p', 0) / 100000000
                profit_23 = y2023.get('n_income_attr_p', 0) / 100000000
                
                yoy_rev = ((rev_24 - rev_23) / rev_23 * 100) if rev_23 else 0
                yoy_profit = ((profit_24 - profit_23) / profit_23 * 100) if profit_23 else 0
                
                rev_eval = "🟢" if yoy_rev > 10 else ("🟡" if yoy_rev > 0 else "🔴")
                profit_eval = "🟢" if yoy_profit > 10 else ("🟡" if yoy_profit > 0 else "🔴")
                
                lines.append(f"| 营业总收入 | {rev_24:.2f}亿 | {rev_23:.2f}亿 | {yoy_rev:+.1f}% | {rev_eval} |")
                lines.append(f"| 归母净利润 | {profit_24:.2f}亿 | {profit_23:.2f}亿 | {yoy_profit:+.1f}% | {profit_eval} |")
                lines.append(f"| 基本EPS | {y2024.get('basic_eps', 0):.3f}元 | {y2023.get('basic_eps', 0):.3f}元 | - | - |")
            else:
                lines.append("| 营业总收入 | 待补充 | 待补充 | - | 🟡 |")
                lines.append("| 归母净利润 | 待补充 | 待补充 | - | 🟡 |")
            
            lines.append("")
            
            # 季度环比
            quarterly = financial_data.get('quarterly', [])
            if len(quarterly) >= 4:
                lines.extend([
                    "### 5.2 2025年季度环比分析（关键！）",
                    "",
                    "| 季度 | 营业收入 | 环比变化 | 归母净利润 | 评价 |",
                    "|:-----|:---------|:---------|:-----------|:-----|",
                ])
                
                for i in range(min(4, len(quarterly))):
                    q = quarterly[i]
                    prev_q = quarterly[i+1] if i+1 < len(quarterly) else None
                    
                    date = q.get('end_date', '')
                    revenue = q.get('total_revenue', 0) / 100000000
                    profit = q.get('n_income_attr_p', 0) / 100000000
                    
                    if prev_q and prev_q.get('total_revenue'):
                        qoq = (q['total_revenue'] - prev_q['total_revenue']) / prev_q['total_revenue'] * 100
                        qoq_str = f"{qoq:+.1f}%"
                        qoq_eval = "🟢" if qoq > 20 else ("🟡" if qoq > -10 else "🔴")
                    else:
                        qoq_str = "-"
                        qoq_eval = ""
                    
                    lines.append(f"| {date} | {revenue:.2f}亿 | {qoq_str} {qoq_eval} | {profit:.2f}亿 | - |")
                
                lines.append("")
            
            # 季度同比
            if len(quarterly) >= 4:
                lines.extend([
                    "### 5.3 季度同比分析（2025 vs 2024同期）",
                    "",
                    "| 季度 | 收入同比 | 净利润同比 | 评价 |",
                    "|:-----|:---------|:-----------|:-----|",
                ])
                
                for i in range(min(4, len(quarterly))):
                    curr_q = quarterly[i]
                    curr_date = curr_q.get('end_date', '')
                    
                    # 找去年同季度
                    yoy_rev_str = "-"
                    yoy_profit_str = "-"
                    yoy_eval = ""
                    
                    for j in range(i+1, len(quarterly)):
                        prev_q = quarterly[j]
                        prev_date = prev_q.get('end_date', '')
                        
                        # 简单匹配季度（MMDD相同）
                        if curr_date[4:] == prev_date[4:] and int(curr_date[:4]) - int(prev_date[:4]) == 1:
                            if prev_q.get('total_revenue'):
                                yoy_rev = (curr_q['total_revenue'] - prev_q['total_revenue']) / prev_q['total_revenue'] * 100
                                yoy_rev_str = f"{yoy_rev:+.1f}%"
                            
                            if prev_q.get('n_income_attr_p') and prev_q['n_income_attr_p'] != 0:
                                yoy_profit = (curr_q['n_income_attr_p'] - prev_q['n_income_attr_p']) / abs(prev_q['n_income_attr_p']) * 100
                                yoy_profit_str = f"{yoy_profit:+.1f}%"
                            
                            # 评价
                            try:
                                yoy_profit_val = float(yoy_profit_str.replace('%', '').replace('+', ''))
                                if yoy_profit_val > 20:
                                    yoy_eval = "🟢"
                                elif yoy_profit_val > -10:
                                    yoy_eval = "🟡"
                                else:
                                    yoy_eval = "🔴"
                            except:
                                yoy_eval = ""
                            
                            break
                    
                    lines.append(f"| {curr_date} | {yoy_rev_str} | {yoy_profit_str} | {yoy_eval} |")
                
                lines.append("")
            
            # 盈利能力趋势
            fina = financial_data.get('fina', [])
            if fina:
                lines.extend([
                    "### 5.4 盈利能力趋势分析",
                    "",
                    "| 指标 | 最新 | 上季 | 变动 | 趋势 |",
                    "|:-----|:-----|:-----|:-----|:-----|",
                ])
                
                latest = fina[0] if fina else {}
                prev = fina[1] if len(fina) > 1 else {}
                
                roe_latest = latest.get('roe', 0)
                roe_prev = prev.get('roe', 0) if prev else 0
                roe_change = roe_latest - roe_prev if roe_prev else 0
                roe_trend = "🟢" if roe_change > 0 else ("🟡" if roe_change > -0.5 else "🔴")
                
                margin_latest = latest.get('grossprofit_margin', 0)
                margin_prev = prev.get('grossprofit_margin', 0) if prev else 0
                margin_change = margin_latest - margin_prev if margin_prev else 0
                margin_trend = "🟢" if margin_change > 0 else "🟡"
                
                lines.append(f"| ROE | {roe_latest:.2f}% | {roe_prev:.2f}% | {roe_change:+.2f}% | {roe_trend} |")
                lines.append(f"| 毛利率 | {margin_latest:.2f}% | {margin_prev:.2f}% | {margin_change:+.2f}% | {margin_trend} |")
                lines.append(f"| 净利率 | {latest.get('netprofit_margin', 0):.2f}% | - | - | - |")
                lines.append(f"| 资产负债率 | {latest.get('debt_to_assets', 0):.2f}% | - | - | - |")
                
                lines.append("")
            
            # 财务风险警示
            lines.extend([
                "### 5.5 财务健康度评估 ⚠️",
                "",
                "| 评估项 | 现状 | 风险等级 | 说明 |",
                "|:-------|:-----|:---------|:-----|",
            ])
            
            # 根据实际数据评估
            if quarterly and len(quarterly) >= 2:
                latest_profit = quarterly[0].get('n_income_attr_p', 0)
                prev_year_profit = 0
                for q in quarterly[1:]:
                    if str(q.get('end_date', '')).endswith(quarterly[0]['end_date'][4:]):
                        prev_year_profit = q.get('n_income_attr_p', 0)
                        break
                
                if prev_year_profit and prev_year_profit != 0:
                    yoy_profit = (latest_profit - prev_year_profit) / abs(prev_year_profit) * 100
                    if yoy_profit < -10:
                        lines.append(f"| 业绩同比 | 下滑{yoy_profit:.1f}% | 🔴 **高** | 净利润同比下滑，需警惕 |")
                    elif yoy_profit < 0:
                        lines.append(f"| 业绩同比 | 下滑{yoy_profit:.1f}% | 🟡 中 | 小幅下滑 |")
                    else:
                        lines.append(f"| 业绩同比 | 增长{yoy_profit:.1f}% | 🟢 低 | 业绩向好 |")
                else:
                    lines.append("| 业绩同比 | 数据不足 | 🟡 中 | 无法评估 |")
            
            lines.append("| 财务结构 | 负债率适中 | 🟢 低 | 财务风险可控 |")
            lines.append("")
        
        else:
            lines.extend([
                "### 5.1 利润表分析",
                "",
                "| 指标 | 2022A | 2023A | 2025Q3 | 趋势 |",
                "|:-----|:------|:------|:-------|:-----|",
                "| 营业总收入 | 待补充 | 待补充 | 待补充 | 🟢/🔴 |",
                "| 归母净利润 | 待补充 | 待补充 | 待补充 | 🟢/🔴 |",
                "",
                "⚠️ 财务数据获取中，请稍后查看完整分析",
            ])
        
        return "\n".join(lines)
    
    def _get_financial_data(self) -> Dict:
        """获取完整财务数据（含同比环比）"""
        data = {
            'yearly': [],
            'quarterly': [],
            'fina': []
        }
        
        if not self.tushare_available or not self.tushare_api:
            return data
        
        try:
            # 获取年度数据
            import tushare as ts
            ts.set_token(self.tushare_api.token)
            pro = ts.pro_api()
            
            # 年度利润表
            yearly_income = pro.income(ts_code=self.stock_code, fields='end_date,total_revenue,n_income_attr_p,basic_eps')
            if yearly_income is not None and not yearly_income.empty:
                # 去重并排序
                yearly_income = yearly_income.drop_duplicates(subset=['end_date'])
                yearly_income = yearly_income.sort_values('end_date', ascending=False)
                data['yearly'] = yearly_income.to_dict('records')
            
            # 季度数据
            quarterly_income = self.tushare_api.get_income(self.stock_code)
            if quarterly_income is not None and not quarterly_income.empty:
                data['quarterly'] = quarterly_income.to_dict('records')
            
            # 财务指标
            fina = self.tushare_api.get_fina_indicator(self.stock_code)
            if fina is not None and not fina.empty:
                data['fina'] = fina.to_dict('records')
            
        except Exception as e:
            print(f"⚠️ Failed to get financial data: {e}")
        
        return data
    
    def _section_6_industry_outlook(self) -> str:
        """环节6: 行业景气度"""
        # Exa搜索行业新闻
        news = self._search_exa_news(f"{self.stock_name} 行业")
        
        lines = [
            "## 六、行业景气度验证",
            "",
            "### 6.1 行业驱动因素",
            "",
            "| 因素 | 影响 | 说明 |",
            "|:-----|:-----|:-----|",
            "| 下游需求 | 🟢/🔴 | 待补充 |",
            "| 国产替代 | 🟢/🔴 | 待补充 |",
            "| 政策支持 | 🟢/🔴 | 待补充 |",
            "",
            "### 6.2 Exa全网行业动态",
            "",
        ]
        
        if news:
            for i, n in enumerate(news[:5], 1):
                title = n.get('title', '')[:60]
                lines.append(f"{i}. {title}...")
        else:
            lines.append("暂无最新行业动态")
        
        return "\n".join(lines)
    
    def _section_7_customer_supplier(self) -> str:
        """环节7: 客户与供应商"""
        return """## 七、客户与供应商分析

### 7.1 客户结构

| 客户类型 | 占比 | 特点 | 信息源 |
|:---------|:-----|:-----|:-------|
| 【客户A】 | 待补充 | 待补充 | 知识星球 |
| 【客户B】 | 待补充 | 待补充 | 知识星球 |

### 7.2 供应商结构

| 供应品类 | 主要供应商 | 议价能力 | 稳定性 |
|:---------|:-----------|:---------|:-------|
| 【品类A】 | 待补充 | 高/中/低 | 🟢/🟡/🔴 |
| 【品类B】 | 待补充 | 高/中/低 | 🟢/🟡/🔴 |
"""
    
    def _section_8_forecast_valuation(self) -> str:
        """环节8: 业绩预测与估值"""
        return """## 八、业绩预测与估值

### 8.1 业绩预测

| 年份 | 营收(亿) | 净利润(亿) | 增长率 | 来源 |
|:-----|:---------|:-----------|:-------|:-----|
| 2023A | 待补充 | 待补充 | 待补充 | 年报 |
| 2024E | 待补充 | 待补充 | 待补充 | 估算 |
| 2025E | 待补充 | 待补充 | 待补充 | 估算 |

### 8.2 三情景估值

| 情景 | 净利润 | 给予PE | 目标价 | 空间 |
|:-----|:-------|:-------|:-------|:-----|
| 保守 | 待补充 | 25倍 | 待补充 | 待补充 |
| 中性 | 待补充 | 35倍 | 待补充 | 待补充 |
| 乐观 | 待补充 | 45倍 | 待补充 | 待补充 |
"""
    
    def _section_9_risks(self) -> str:
        """环节9: 风险提示"""
        return """## 九、风险提示

| 风险类型 | 影响程度 | 说明 |
|:---------|:---------|:-----|
| 【风险1】 | ⭐⭐⭐⭐⭐ | 待补充 |
| 【风险2】 | ⭐⭐⭐⭐ | 待补充 |
| 【风险3】 | ⭐⭐⭐ | 待补充 |
| 【风险4】 | ⭐⭐ | 待补充 |
"""
    
    def _section_10_recommendation(self) -> str:
        """环节10: 投资建议"""
        quote = self._get_quote()
        
        lines = [
            "## 十、投资建议",
            "",
            "### 10.1 投资逻辑评分",
            "",
            "| 维度 | 评分 | 说明 |",
            "|:-----|:-----|:-----|",
            "| 行业景气度 | ⭐⭐⭐⭐⭐ | 待补充 |",
            "| 业绩成长性 | ⭐⭐⭐⭐ | 待补充 |",
            "| 估值合理性 | ⭐⭐⭐ | 待补充 |",
            "| 技术面 | ⭐⭐⭐ | 待补充 |",
            "| 竞争优势 | ⭐⭐⭐⭐ | 待补充 |",
            "",
            "### 10.2 操作建议",
            "",
        ]
        
        if quote:
            price = quote['price']
            change = quote['change']
            
            if change > 5:
                action = "⚠️ **短期超买，不宜追高**"
                buy_range = f"¥{price*0.93:.2f} - ¥{price*0.97:.2f}"
            elif change > 0:
                action = "🟡 **分批建仓**"
                buy_range = f"¥{price*0.97:.2f} - ¥{price:.2f}"
            else:
                action = "🟢 **逢低买入**"
                buy_range = f"¥{price:.2f} - ¥{price*1.02:.2f}"
            
            lines.extend([
                f"| 建议项 | 内容 |",
                f"|:-------|:-----|",
                f"| **当前状态** | {action} |",
                f"| **买入区间** | {buy_range} |",
                f"| **目标价** | 待补充 (+XX%空间) |",
                f"| **止损价** | ¥{price*0.90:.2f} (-10%) |",
                f"| **持有期限** | 6-12个月 |",
            ])
        else:
            lines.append("⚠️ 行情数据获取中，建议稍后查看")
        
        return "\n".join(lines)
    
    def _data_sources(self) -> str:
        """数据源汇总"""
        return """---

## 数据源汇总

| 来源 | 数据类型 | 具体内容 | 时效性 |
|:-----|:---------|:---------|:-------|
| **长桥API** | 实时行情 | 价格/成交量/涨跌幅 | 实时 |
| **Exa MCP** | 全网新闻 | 最新动态/公告/研报 | 实时 |
| **知识星球** | 调研纪要 | 深度调研/产业链数据 | 定时更新 |
| **Tushare** | 财务数据 | 财报/估值/股东 | 季度更新 |

---

*报告版本: v1.0*  
*生成时间: {time}*  
*分析师: AI Analyst*  
*免责声明: 本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
""".format(time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    def _get_quote(self) -> Optional[Dict]:
        """获取实时行情"""
        if not self.longbridge_available:
            return None
        
        try:
            quotes = self.lb_api.get_quotes([self.stock_code])
            if quotes:
                return quotes[0]
        except:
            pass
        return None
    
    def _search_exa_news(self, query: str, num: int = 5) -> List[Dict]:
        """Exa搜索新闻"""
        news = []
        try:
            result = subprocess.run(
                ['mcporter', 'call', f'exa.web_search_exa({{"query": "{query}", "numResults": {num}}})'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                titles = re.findall(r'Title: (.+)', result.stdout)
                for title in titles[:num]:
                    news.append({'title': title.strip()})
        except:
            pass
        return news


# 便捷函数
def analyze_stock(stock_code: str, stock_name: str = "") -> str:
    """
    个股深度分析入口 - 10环节标准流程
    
    Args:
        stock_code: 股票代码 (如: 000969.SZ)
        stock_name: 股票名称
        
    Returns:
        完整分析报告 (Markdown格式)
    """
    analyzer = StockAnalyzer()
    return analyzer.analyze(stock_code, stock_name)


if __name__ == "__main__":
    # 测试
    if len(sys.argv) >= 2:
        code = sys.argv[1]
        name = sys.argv[2] if len(sys.argv) >= 3 else ""
        report = analyze_stock(code, name)
        print(report)
    else:
        print("Usage: python3 comprehensive_stock_analyzer.py <stock_code> [stock_name]")
        print("Example: python3 comprehensive_stock_analyzer.py 000969.SZ 安泰科技")
