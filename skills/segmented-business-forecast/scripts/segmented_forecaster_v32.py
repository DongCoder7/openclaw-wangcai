#!/root/.openclaw/workspace/venv/bin/python3
"""
业务线拆分估值分析器 v3.2 - 主力产品单独搜 + 其他用行业平均

核心策略:
1. 批量搜索获取行业全景（所有产品的平均数据）
2. 识别主要产品，按收入权重排序
3. 收入权重>20%的主力产品 → 单独搜索（精确数据）
4. 收入权重<20%的其他产品 → 用行业平均数据
5. 汇总预测

搜索次数:
- 批量搜索: 1次（行业全景）
- 主力产品单独搜: 2-3次（每个产品1次）
- 市占率搜索: 1次（公司整体）
- 总计: 4-5次搜索（vs v3的18-30次）

精度 vs 速度的平衡:
- 主力产品（占收入60-80%）有精确数据
- 次要产品（占收入20-40%）用行业平均
"""

import sys
import os
import json
import subprocess
import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, '/root/.openclaw/workspace/tools')

import tushare as ts
import requests


@dataclass
class ProductLine:
    name: str
    parent_segment: str
    
    # 搜索得到的数据
    industry_shipment_growth: float = 0.0
    company_market_share: float = 0.0
    asp_change: float = 0.0
    
    # 基期数据
    revenue_base: float = 0.0
    profit_base: float = 0.0
    margin: float = 0.0
    
    # 预测结果
    revenue_forecast: float = 0.0
    profit_forecast: float = 0.0
    
    # 数据来源
    data_sources: List[str] = field(default_factory=list)
    search_evidence: List[str] = field(default_factory=list)
    is_key_product: bool = False  # 是否主力产品（单独搜索）


@dataclass
class BusinessSegment:
    name: str
    revenue: float
    profit: float
    revenue_pct: float
    profit_pct: float
    margin: float
    product_lines: List[ProductLine] = field(default_factory=list)


class V32Forecaster:
    """v3.2 主力产品单独搜索版"""
    
    def __init__(self, tushare_token: Optional[str] = None):
        if tushare_token:
            self.pro = ts.pro_api(tushare_token)
        else:
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
        
        self.stock_code: str = ""
        self.stock_name: str = ""
        self.segments: List[BusinessSegment] = []
        self.report_period: str = ""
        self._search_cache: Dict[str, List[Dict]] = {}
    
    def load_stock(self, code: str, name: str = ""):
        self.stock_code = code
        self.stock_name = name
        print(f"\n{'='*75}")
        print(f"业务线拆分估值 v3.2: {name} ({code})")
        print(f"策略: 主力产品(>20%)单独搜 + 其他用行业平均")
        print(f"{'='*75}")
    
    def fetch_business_segments(self) -> List[BusinessSegment]:
        print("\n📊 Step 1: 获取财报业务拆分...")
        
        year = datetime.now().year
        periods = [f"{y}1231" for y in range(year, year-3, -1)] + [f"{y}0630" for y in range(year, year-3, -1)]
        
        best_df = None
        best_period = None
        for period in periods:
            try:
                df = self.pro.fina_mainbz(ts_code=self.stock_code, period=period, type='P')
                if df is not None and len(df) > 0:
                    best_df = df
                    best_period = period
                    break
            except:
                continue
        
        if best_df is None:
            return []
        
        self.report_period = best_period
        segments = []
        total_rev = 0.0
        total_prof = 0.0
        
        for _, row in best_df.iterrows():
            name = str(row.get('bz_item', '')).strip()
            sales = float(row.get('bz_sales', 0)) / 1e8
            profit = float(row.get('bz_profit', 0)) / 1e8
            if sales <= 0:
                continue
            total_rev += sales
            total_prof += profit
            segments.append(BusinessSegment(
                name=name, revenue=sales, profit=profit,
                revenue_pct=0.0, profit_pct=0.0,
                margin=profit/sales if sales > 0 else 0
            ))
        
        for seg in segments:
            seg.revenue_pct = seg.revenue / total_rev if total_rev > 0 else 0
            seg.profit_pct = seg.profit / total_prof if total_prof != 0 else 0
        
        segments.sort(key=lambda x: x.revenue_pct, reverse=True)
        self.segments = segments
        
        print(f"   ✅ {best_period}数据, {len(segments)}个业务线")
        print(f"   总营收: {total_rev:.2f}亿 | 总利润: {total_prof:.2f}亿")
        return segments
    
    # ========== 搜索模块（带缓存） ==========
    
    def _search_exa(self, query: str, num: int = 5, timeout: int = 20) -> List[Dict]:
        cache_key = f"{query}:{num}"
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]
        
        try:
            result = subprocess.run(
                ['mcporter', 'call', 'exa.web_search_exa',
                 f'query={query}', f'numResults={num}'],
                capture_output=True, text=True, timeout=timeout
            )
            items = self._parse_exa(result.stdout)
            self._search_cache[cache_key] = items
            return items
        except Exception as e:
            print(f"   ⚠️ Exa搜索失败: {e}")
            return []
    
    def _parse_exa(self, output: str) -> List[Dict]:
        items = []
        current = {}
        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('Title:'):
                if current:
                    items.append(current)
                current = {'title': line[6:].strip(), 'content': ''}
            elif line.startswith('URL:'):
                current['url'] = line[4:].strip()
            elif line and current and not line.startswith('---'):
                current['content'] += ' ' + line
        if current:
            items.append(current)
        for item in items:
            item['full_text'] = (item.get('title', '') + ' ' + item.get('content', '')).lower()
        return items
    
    def _extract_growth(self, text: str) -> Optional[float]:
        patterns = [
            r'(\d+(?:\.\d+)?)\s*%\s*(?:同比)?增长',
            r'grow\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*%',
            r'growth\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%',
            r'同比增长\s*(\d+(?:\.\d+)?)\s*%',
            r'CAGR\s*(\d+(?:\.\d+)?)\s*%',
            r'出货量\s*(\d+(?:\.\d+)?)\s*%',
            r'增长\s*(\d+(?:\.\d+)?)\s*%',
        ]
        for p in patterns:
            for m in re.findall(p, text, re.IGNORECASE):
                try:
                    val = float(m.replace(',', ''))
                    if 0 < val < 500:
                        return val / 100
                except:
                    continue
        return None
    
    def _extract_asp_change(self, text: str) -> Optional[float]:
        # 尝试提取具体百分比
        price_patterns = [
            r'(?:降价|降价幅度).*?(\d+(?:\.\d+)?)\s*%',
            r'(?:涨价|涨价幅度).*?(\d+(?:\.\d+)?)\s*%',
            r'ASP.*?(?:下降|降低).*?(\d+(?:\.\d+)?)\s*%',
            r'ASP.*?(?:上升|涨).*?(\d+(?:\.\d+)?)\s*%',
            r'价格.*?(?:下降|跌).*?(\d+(?:\.\d+)?)\s*%',
            r'价格.*?(?:上升|涨).*?(\d+(?:\.\d+)?)\s*%',
        ]
        for p in price_patterns:
            for m in re.findall(p, text, re.IGNORECASE):
                try:
                    val = float(m)
                    if 0 < val < 35:  # 光模块年降通常<30%，过滤极端值
                        return -val / 100 if any(k in text for k in ['降', '跌', 'cut', '下降']) else val / 100
                except:
                    continue
        
        # 定性判断
        up_signals = ['涨价', '价格上涨', '提价', 'ASP提升', '均价上涨', '涨价函']
        down_signals = ['降价', '价格下跌', '价格战', 'ASP下降', '均价下跌', '降价潮']
        
        up_count = sum(1 for s in up_signals if s in text)
        down_count = sum(1 for s in down_signals if s in text)
        
        if up_count > down_count and up_count > 0:
            return 0.05
        elif down_count > up_count and down_count > 0:
            return -0.05
        return 0.0
    
    def _extract_market_share(self, text: str, company_name: str) -> Optional[float]:
        name_patterns = [company_name, company_name.replace(' ', ''), company_name.lower().replace(' ', '')]
        for name in name_patterns:
            patterns = [
                rf'{name}.*?市占率\s*(\d+(?:\.\d+)?)\s*%',
                rf'{name}.*?市场份额\s*(\d+(?:\.\d+)?)\s*%',
                rf'市占率.*?{name}.*?(\d+(?:\.\d+)?)\s*%',
                rf'{name}.*?占比\s*(\d+(?:\.\d+)?)\s*%',
            ]
            for p in patterns:
                for m in re.findall(p, text, re.IGNORECASE):
                    try:
                        val = float(m.replace(',', ''))
                        if 0 < val < 100:
                            return val / 100
                    except:
                        continue
        return None
    
    # ========== 核心流程 ==========
    
    def search_and_forecast_segment(self, segment: BusinessSegment) -> BusinessSegment:
        """
        v3.2 核心流程:
        1. 批量搜索行业全景（获取行业平均数据）
        2. 识别主要产品
        3. 分配收入权重
        4. 收入权重>20%的主力产品 → 单独搜索
        5. 收入权重<20%的其他产品 → 用行业平均
        6. 汇总预测
        """
        print(f"\n{'='*75}")
        print(f"业务线预测: [{segment.name}]")
        print(f"{'='*75}")
        
        # === Step 2: 批量搜索行业全景 ===
        print(f"\n🔍 Step 2: 批量搜索行业全景...")
        year = datetime.now().year
        industry_query = f"{segment.name} 行业 {year} 出货量 增长 ASP 价格 预测 LightCounting"
        
        print(f"   搜索: {industry_query[:55]}...")
        industry_items = self._search_exa(industry_query, 5, 25)
        
        all_text = " ".join([i.get('full_text', '') for i in industry_items])
        
        # 提取行业平均数据
        industry_growth = self._extract_growth(all_text)
        industry_asp = self._extract_asp_change(all_text)
        
        if industry_growth is None:
            industry_growth = 0.20  # 默认20%
            print(f"   ⚠️ 未找到行业增长数据，使用默认: +20%")
        else:
            print(f"   ✅ 行业出货增长: {industry_growth:+.1%}")
        
        if industry_asp == 0.0:
            industry_asp = -0.05  # 默认年降5%
            print(f"   ⚠️ 未找到ASP变化，使用默认: -5%")
        else:
            print(f"   ✅ 行业ASP变化: {industry_asp:+.1%}")
        
        # === Step 3: 识别主要产品 ===
        print(f"\n📋 Step 3: 识别主要产品...")
        product_types = self._identify_products(all_text, segment)
        
        # 分配收入权重
        products = self._create_products_with_weights(product_types, segment)
        
        # 标记主力产品 (>20%收入权重)
        for pl in products:
            weight = pl.revenue_base / segment.revenue if segment.revenue > 0 else 0
            pl.is_key_product = weight > 0.20
            if pl.is_key_product:
                print(f"   ⭐ 主力产品: {pl.name} (收入权重{weight:.1%})")
        
        # === Step 4: 主力产品单独搜索 ===
        print(f"\n🔍 Step 4: 主力产品单独搜索...")
        for pl in products:
            if pl.is_key_product:
                print(f"\n   单独搜索 [{pl.name}]...")
                self._search_key_product(pl, all_text)
                time.sleep(0.3)
            else:
                # 非主力产品用行业平均
                pl.industry_shipment_growth = industry_growth
                pl.asp_change = industry_asp
                pl.search_evidence.append(f"行业平均: 出货{industry_growth:+.1%}, ASP{industry_asp:+.1%}")
        
        # === Step 5: 搜索公司市占率（一次） ===
        print(f"\n🔍 Step 5: 搜索公司市占率...")
        self._search_market_share(products, all_text)
        
        # === Step 6: 预测 ===
        print(f"\n📈 Step 6: 分产品预测...")
        total_forecast_revenue = 0.0
        total_forecast_profit = 0.0
        
        for pl in products:
            self._forecast_product(pl)
            total_forecast_revenue += pl.revenue_forecast
            total_forecast_profit += pl.profit_forecast
        
        segment.product_lines = products
        segment.forecast_revenue = total_forecast_revenue
        segment.forecast_profit = total_forecast_profit
        
        # 输出汇总
        self._print_segment_summary(segment, products)
        
        return segment
    
    def _identify_products(self, text: str, segment: BusinessSegment) -> List[str]:
        """识别主要产品类型"""
        products = []
        
        if '光模块' in segment.name or '光通讯' in segment.name or '光通信' in segment.name:
            # 按优先级排序（高端产品优先）
            if '1.6t' in text or '800g' in text:
                products.append('800G/1.6T高速光模块')
            if 'npo' in text or 'cpo' in text:
                products.append('NPO/CPO')
            if '硅光' in text or 'silicon' in text:
                products.append('硅光模块')
            if '400g' in text:
                products.append('400G光模块')
            if '200g' in text:
                products.append('200G光模块')
            if '100g' in text or '50g' in text or '25g' in text:
                products.append('100G及以下光模块')
            
            # 如果没识别到，用默认
            if not products:
                products = ['800G/1.6T高速光模块', '400G/200G光模块', '100G及以下光模块']
        else:
            products = [segment.name]
        
        return products
    
    def _create_products_with_weights(self, product_types: List[str], segment: BusinessSegment) -> List[ProductLine]:
        """创建产品并分配收入权重"""
        # ASP权重（用于分配收入）
        asp_weights = {
            '800G/1.6T高速光模块': 8.0,
            'NPO/CPO': 10.0,
            '硅光模块': 6.0,
            '400G光模块': 3.0,
            '200G光模块': 1.5,
            '400G/200G光模块': 3.0,
            '100G及以下光模块': 1.0,
        }
        
        products = []
        weights = []
        
        for prod_name in product_types:
            w = asp_weights.get(prod_name, 1.0)
            weights.append(w)
            pl = ProductLine(name=prod_name, parent_segment=segment.name)
            products.append(pl)
        
        # 分配收入
        total_weight = sum(weights)
        for i, pl in enumerate(products):
            weight_pct = weights[i] / total_weight
            pl.revenue_base = segment.revenue * weight_pct
            pl.profit_base = segment.profit * weight_pct
            pl.margin = pl.profit_base / pl.revenue_base if pl.revenue_base > 0 else segment.margin
        
        return products
    
    def _search_key_product(self, pl: ProductLine, all_text: str):
        """单独搜索主力产品"""
        # 搜索该产品专属数据
        query = f"{pl.name} 2025 2026 出货量 出货增长 ASP 价格趋势"
        items = self._search_exa(query, 3, 15)
        
        text = " ".join([i.get('full_text', '') for i in items])
        
        # 提取该产品专属数据
        growth = self._extract_growth(text)
        if growth is not None:
            pl.industry_shipment_growth = growth
            pl.search_evidence.append(f"单独搜索: 出货{growth:+.1%}")
            print(f"      ✅ 出货增长: {growth:+.1%}")
        else:
            # 用行业平均
            industry_growth = self._extract_growth(all_text) or 0.20
            pl.industry_shipment_growth = industry_growth
            pl.search_evidence.append(f"行业平均: 出货{industry_growth:+.1%}")
            print(f"      ⚠️ 未找到专属数据，用行业平均: {industry_growth:+.1%}")
        
        asp = self._extract_asp_change(text)
        if asp != 0.0:
            pl.asp_change = asp
            pl.search_evidence.append(f"单独搜索: ASP{asp:+.1%}")
            print(f"      ✅ ASP变化: {asp:+.1%}")
        else:
            industry_asp = self._extract_asp_change(all_text) or -0.05
            pl.asp_change = industry_asp
            pl.search_evidence.append(f"行业平均: ASP{industry_asp:+.1%}")
            print(f"      ⚠️ 未找到专属数据，用行业平均: {industry_asp:+.1%}")
    
    def _search_market_share(self, products: List[ProductLine], all_text: str):
        """搜索公司市占率"""
        share = self._extract_market_share(all_text, self.stock_name)
        
        if share is None:
            # 补搜
            query = f"{self.stock_name} 市占率 市场份额 光模块"
            items = self._search_exa(query, 3, 15)
            text = " ".join([i.get('full_text', '') for i in items])
            share = self._extract_market_share(text, self.stock_name)
        
        for pl in products:
            if share is not None:
                pl.company_market_share = share
                pl.search_evidence.append(f"市占率{share:.1%}")
            else:
                # 默认市占率
                defaults = {
                    '800G/1.6T高速光模块': 0.40,
                    'NPO/CPO': 0.25,
                    '硅光模块': 0.20,
                    '400G光模块': 0.30,
                    '200G光模块': 0.25,
                    '400G/200G光模块': 0.30,
                    '100G及以下光模块': 0.15,
                }
                pl.company_market_share = defaults.get(pl.name, 0.20)
                pl.search_evidence.append(f"默认市占率{pl.company_market_share:.1%}")
        
        if share is not None:
            print(f"   ✅ 公司市占率: {share:.1%}")
        else:
            print(f"   ⚠️ 未找到市占率，使用产品默认值")
    
    def _forecast_product(self, pl: ProductLine):
        """预测单个产品"""
        revenue_factor = (1 + pl.industry_shipment_growth) * (1 + pl.asp_change)
        pl.revenue_forecast = pl.revenue_base * revenue_factor
        
        scale_effect = min(0.02, max(-0.02, pl.industry_shipment_growth * 0.05))
        forecast_margin = pl.margin + scale_effect
        forecast_margin = max(0.05, min(0.60, forecast_margin))
        pl.profit_forecast = pl.revenue_forecast * forecast_margin
    
    def _print_segment_summary(self, segment: BusinessSegment, products: List[ProductLine]):
        """打印业务线汇总"""
        print(f"\n📋 [{segment.name}] 预测汇总:")
        print(f"{'产品':<25} {'类型':<8} {'出货增长':>8} {'ASP':>8} {'基期营收':>10} {'预测营收':>10} {'变化':>8}")
        print(f"{'─'*90}")
        
        for pl in products:
            rev_chg = (pl.revenue_forecast - pl.revenue_base) / pl.revenue_base if pl.revenue_base > 0 else 0
            prod_type = "⭐主力" if pl.is_key_product else " 其他"
            print(f"{pl.name:<25} {prod_type:<8} {pl.industry_shipment_growth:>+7.1%} {pl.asp_change:>+7.1%} {pl.revenue_base:>10.2f} {pl.revenue_forecast:>10.2f} {rev_chg:>+7.1%}")
        
        print(f"{'─'*90}")
        rev_chg = (segment.forecast_revenue - segment.revenue) / segment.revenue
        prof_chg = (segment.forecast_profit - segment.profit) / segment.profit
        print(f"{'合计':<25} {'':8} {'':8} {'':8} {segment.revenue:>10.2f} {segment.forecast_revenue:>10.2f} {rev_chg:>+7.1%}")
        print(f"{'':25} {'':8} {'':8} {'':8} {'利润:':>10} {segment.forecast_profit:>10.2f} {prof_chg:>+7.1%}")
    
    def run_forecast(self) -> Dict:
        """执行完整流程"""
        self.fetch_business_segments()
        if not self.segments:
            return {}
        
        for segment in self.segments:
            self.search_and_forecast_segment(segment)
            time.sleep(0.3)
        
        return self.summarize()
    
    def summarize(self) -> Dict:
        """汇总"""
        print(f"\n{'='*75}")
        print("汇总预测结果")
        print(f"{'='*75}")
        
        total_base_revenue = sum(s.revenue for s in self.segments)
        total_base_profit = sum(s.profit for s in self.segments)
        total_forecast_revenue = sum(s.forecast_revenue for s in self.segments)
        total_forecast_profit = sum(s.forecast_profit for s in self.segments)
        
        rev_change = (total_forecast_revenue - total_base_revenue) / total_base_revenue
        profit_change = (total_forecast_profit - total_base_profit) / total_base_profit
        
        print(f"\n{'业务线':<25} {'基期营收':>10} {'预测营收':>10} {'变化':>8} {'基期利润':>10} {'预测利润':>10} {'变化':>8}")
        print(f"{'─'*85}")
        for seg in self.segments:
            rev_chg = (seg.forecast_revenue - seg.revenue) / seg.revenue
            prof_chg = (seg.forecast_profit - seg.profit) / seg.profit
            print(f"{seg.name:<25} {seg.revenue:>10.2f} {seg.forecast_revenue:>10.2f} {rev_chg:>+7.1%} {seg.profit:>10.2f} {seg.forecast_profit:>10.2f} {prof_chg:>+7.1%}")
        print(f"{'─'*85}")
        print(f"{'合计':<25} {total_base_revenue:>10.2f} {total_forecast_revenue:>10.2f} {rev_change:>+7.1%} {total_base_profit:>10.2f} {total_forecast_profit:>10.2f} {profit_change:>+7.1%}")
        print(f"{'='*75}")
        
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'base_revenue': total_base_revenue,
            'forecast_revenue': total_forecast_revenue,
            'base_profit': total_base_profit,
            'forecast_profit': total_forecast_profit,
            'revenue_change': rev_change,
            'profit_change': profit_change
        }
    
    def generate_report(self) -> str:
        """生成Markdown报告"""
        result = self.summarize()
        if not result:
            return "无法生成报告"
        
        lines = []
        lines.append(f"# {self.stock_name} ({self.stock_code}) 业务线拆分估值 v3.2")
        lines.append(f"\n> **分析日期**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"> **基准报告期**: {self.report_period}")
        lines.append(f"> **策略**: 主力产品(>20%)单独搜 + 其他用行业平均")
        lines.append("")
        
        for seg in self.segments:
            lines.append(f"## {seg.name}")
            lines.append("")
            lines.append(f"- **基期营收**: {seg.revenue:.2f}亿 (占比{seg.revenue_pct:.1%})")
            lines.append("")
            
            if seg.product_lines:
                lines.append("**细分产品预测**:")
                lines.append("")
                lines.append("| 产品 | 类型 | 出货增长 | ASP变化 | 市占率 | 基期营收 | 预测营收 | 变化 | 数据来源 |")
                lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|")
                for pl in seg.product_lines:
                    rev_chg = (pl.revenue_forecast - pl.revenue_base) / pl.revenue_base if pl.revenue_base > 0 else 0
                    prod_type = "⭐主力" if pl.is_key_product else "其他"
                    evidence = ' | '.join(pl.search_evidence[:2])
                    lines.append(f"| {pl.name} | {prod_type} | {pl.industry_shipment_growth:+.1%} | {pl.asp_change:+.1%} | {pl.company_market_share:.1%} | {pl.revenue_base:.2f}亿 | {pl.revenue_forecast:.2f}亿 | {rev_chg:+.1%} | {evidence} |")
                lines.append("")
        
        lines.append("## 汇总预测")
        lines.append("")
        lines.append("| 指标 | 基期 | 预测 | 变化 |")
        lines.append("|:---|---:|---:|---:|")
        lines.append(f"| 总营收 | {result['base_revenue']:.2f}亿 | {result['forecast_revenue']:.2f}亿 | {result['revenue_change']:+.1%} |")
        lines.append(f"| 总利润 | {result['base_profit']:.2f}亿 | {result['forecast_profit']:.2f}亿 | {result['profit_change']:+.1%} |")
        lines.append("")
        
        lines.append("## 核心假设")
        lines.append("")
        lines.append("1. **主力产品**: 收入权重>20%的产品单独搜索精确数据")
        lines.append("2. **其他产品**: 收入权重<20%的产品使用行业平均数据")
        lines.append("3. **市占率不变**: 假设公司各产品市占率维持基期水平")
        lines.append("4. **原料成本不变**: 已内含在利润率中")
        lines.append("")
        
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='业务线拆分估值 v3.2')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--name', '-n', default='', help='股票名称')
    parser.add_argument('--output', '-o', default='', help='输出路径')
    args = parser.parse_args()
    
    forecaster = V32Forecaster()
    forecaster.load_stock(args.code, args.name)
    result = forecaster.run_forecast()
    
    if result:
        report = forecaster.generate_report()
        print("\n" + report)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(report)
            print(f"\n✅ 报告已保存: {args.output}")


if __name__ == '__main__':
    main()
