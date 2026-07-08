#!/root/.openclaw/workspace/venv/bin/python3
"""
业务线拆分估值分析器 v3.1 - 搜索优化版

核心优化(vs v3):
1. 合并搜索: 一次搜索获取多个产品信息，不是每个产品单独搜
2. 批量提取: 从搜索结果中批量提取各产品的量价数据
3. 缓存机制: 相同搜索不重复执行
4. 减少轮次: 从3轮/产品 → 1-2轮/业务线

搜索策略:
- 业务线级别: 搜一次行业全景 (包含所有产品出货量、ASP、技术趋势)
- 产品级别: 只搜缺失的关键数据
- 市占率: 一次搜索公司整体市占率
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
    """细分产品线"""
    name: str
    parent_segment: str
    
    # 从搜索结果提取的数据
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


@dataclass
class BusinessSegment:
    """业务线"""
    name: str
    revenue: float
    profit: float
    revenue_pct: float
    profit_pct: float
    margin: float
    product_lines: List[ProductLine] = field(default_factory=list)


class OptimizedForecaster:
    """优化版业务线拆分估值分析器"""
    
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
        
        # 搜索缓存
        self._search_cache: Dict[str, List[Dict]] = {}
    
    def load_stock(self, code: str, name: str = ""):
        self.stock_code = code
        self.stock_name = name
        print(f"\n{'='*75}")
        print(f"业务线拆分估值分析 v3.1: {name} ({code})")
        print(f"{'='*75}")
    
    def fetch_business_segments(self) -> List[BusinessSegment]:
        """获取分业务数据"""
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
        
        print(f"   ✅ 获取到{best_period}数据, {len(segments)}个业务线")
        print(f"   总营收: {total_rev:.2f}亿 | 总利润: {total_prof:.2f}亿")
        return segments
    
    # ========== 优化搜索模块 ==========
    
    def _search_exa(self, query: str, num: int = 5, timeout: int = 20) -> List[Dict]:
        """Exa搜索，带缓存和超时"""
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
            print(f"   Exa搜索失败: {e}")
            return []
    
    def _parse_exa(self, output: str) -> List[Dict]:
        """解析Exa输出"""
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
        """提取增长率"""
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
        """提取ASP变化"""
        # 先尝试提取具体百分比
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
                    if 0 < val < 100:
                        return -val / 100 if any(k in text for k in ['降', '跌', 'cut', '下降']) else val / 100
                except:
                    continue
        
        # 定性判断
        up_signals = ['涨价', '价格上涨', '提价', 'ASP提升', '均价上涨', '涨价函', '涨价潮']
        down_signals = ['降价', '价格下跌', '价格战', 'ASP下降', '均价下跌', '降价潮', '价格竞争']
        
        up_count = sum(1 for s in up_signals if s in text)
        down_count = sum(1 for s in down_signals if s in text)
        
        if up_count > down_count and up_count > 0:
            return 0.05
        elif down_count > up_count and down_count > 0:
            return -0.05
        return 0.0
    
    def _extract_market_share(self, text: str, company_name: str) -> Optional[float]:
        """提取市占率"""
        # 直接匹配公司名称+市占率
        name_patterns = [
            company_name,
            company_name.replace(' ', ''),
            company_name.lower().replace(' ', ''),
        ]
        for name in name_patterns:
            patterns = [
                rf'{name}.*?市占率\s*(\d+(?:\.\d+)?)\s*%',
                rf'{name}.*?市场份额\s*(\d+(?:\.\d+)?)\s*%',
                rf'市占率.*?{name}.*?(\d+(?:\.\d+)?)\s*%',
                rf'market share.*?{name}.*?\s*(\d+(?:\.\d+)?)\s*%',
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
    
    # ========== 核心优化: 合并搜索 ==========
    
    def search_industry_batch(self, segment: BusinessSegment) -> Dict[str, ProductLine]:
        """
        优化版: 一次搜索获取业务线所有产品的行业数据
        
        搜索策略:
        1. 搜行业全景 (包含所有产品出货量、ASP、技术趋势)
        2. 从结果中批量提取各产品的数据
        3. 只补搜缺失的关键数据
        """
        print(f"\n🔍 Step 2: 批量搜索 [{segment.name}] 行业数据...")
        
        # 1. 行业全景搜索 (一次搜索覆盖所有产品)
        year = datetime.now().year
        industry_query = f"{segment.name} 行业 2025 {year} 出货量 ASP 价格 800G 1.6T 400G 200G 100G 光模块 LightCounting"
        
        print(f"   搜索: {industry_query[:60]}...")
        industry_items = self._search_exa(industry_query, 5, 25)
        
        if not industry_items:
            print(f"   ⚠️ 行业搜索无结果，使用默认值")
            return self._create_default_products(segment)
        
        # 合并所有文本用于分析
        all_text = " ".join([i.get('full_text', '') for i in industry_items])
        
        print(f"   ✅ 获取到{len(industry_items)}条结果，分析中...")
        
        # 2. 识别主要产品类型
        product_types = self._identify_products_from_text(all_text, segment)
        print(f"   识别到产品类型: {', '.join(product_types)}")
        
        # 3. 从文本中提取各产品数据
        products = {}
        for prod_name in product_types:
            pl = self._extract_product_data(prod_name, all_text, industry_items)
            products[prod_name] = pl
        
        # 4. 补搜缺失数据 (只搜缺失的，不是每个都搜)
        missing_products = [name for name, pl in products.items() if pl.industry_shipment_growth == 0.0]
        if missing_products:
            print(f"   补搜缺失数据: {', '.join(missing_products)}")
            for prod_name in missing_products:
                self._supplement_product_data(prod_name, products[prod_name])
                time.sleep(0.3)
        
        # 5. 搜索公司市占率 (一次)
        self._search_company_market_share(products, all_text)
        
        return products
    
    def _identify_products_from_text(self, text: str, segment: BusinessSegment) -> List[str]:
        """从搜索结果文本中识别主要产品类型"""
        products = []
        
        if '光模块' in segment.name or '光通讯' in segment.name:
            # 光模块产品识别
            if '800g' in text or '1.6t' in text:
                products.append('800G/1.6T高速光模块')
            if '400g' in text:
                products.append('400G光模块')
            if '200g' in text:
                products.append('200G光模块')
            if '100g' in text or '50g' in text or '25g' in text:
                products.append('100G及以下光模块')
            if 'npo' in text or 'cpo' in text:
                products.append('NPO/CPO')
            if '硅光' in text or 'silicon photonic' in text:
                products.append('硅光模块')
            
            # 如果没识别到，用默认
            if not products:
                products = ['800G/1.6T高速光模块', '400G/200G光模块', '100G及以下光模块']
        else:
            # 其他业务不拆分
            products = [segment.name]
        
        return products
    
    def _extract_product_data(self, prod_name: str, all_text: str, items: List[Dict]) -> ProductLine:
        """从搜索结果文本中提取单个产品的数据"""
        pl = ProductLine(name=prod_name, parent_segment='')
        
        # 提取该产品相关的文本片段
        prod_keywords = self._get_product_keywords(prod_name)
        prod_text = ""
        for item in items:
            text = item.get('full_text', '')
            if any(k in text for k in prod_keywords):
                prod_text += text + " "
        
        # 提取出货量增长
        growth = self._extract_growth(prod_text)
        if growth is not None:
            pl.industry_shipment_growth = growth
            pl.search_evidence.append(f"出货增长{growth:+.1%}")
        else:
            # 从通用文本提取
            growth = self._extract_growth(all_text)
            if growth is not None:
                pl.industry_shipment_growth = growth
                pl.search_evidence.append(f"行业整体增长{growth:+.1%}")
        
        # 提取ASP变化
        asp_change = self._extract_asp_change(prod_text)
        if asp_change != 0.0:
            pl.asp_change = asp_change
            pl.search_evidence.append(f"ASP{asp_change:+.1%}")
        else:
            asp_change = self._extract_asp_change(all_text)
            pl.asp_change = asp_change
            if asp_change != 0.0:
                pl.search_evidence.append(f"行业ASP{asp_change:+.1%}")
        
        # 如果没有数据，使用默认值
        if pl.industry_shipment_growth == 0.0:
            pl.industry_shipment_growth = self._default_growth(prod_name)
            pl.search_evidence.append(f"默认值: {pl.industry_shipment_growth:+.1%}")
        
        if pl.asp_change == 0.0:
            pl.asp_change = self._default_asp_change(prod_name)
            pl.search_evidence.append(f"默认值: {pl.asp_change:+.1%}")
        
        pl.data_sources = ['Exa AI Search']
        return pl
    
    def _get_product_keywords(self, prod_name: str) -> List[str]:
        """获取产品关键词用于文本匹配"""
        keywords = {
            '800G/1.6T高速光模块': ['800g', '1.6t', '高速光模块', '高端光模块'],
            '400G光模块': ['400g'],
            '200G光模块': ['200g'],
            '400G/200G光模块': ['400g', '200g'],
            '100G及以下光模块': ['100g', '50g', '25g', '低速'],
            'NPO/CPO': ['npo', 'cpo', '近封装', '共封装'],
            '硅光模块': ['硅光', 'silicon photonic'],
        }
        return keywords.get(prod_name, [prod_name.lower()])
    
    def _default_growth(self, prod_name: str) -> float:
        """默认增长率"""
        defaults = {
            '800G/1.6T高速光模块': 0.35,
            '400G光模块': 0.15,
            '200G光模块': 0.05,
            '400G/200G光模块': 0.10,
            '100G及以下光模块': -0.10,
            'NPO/CPO': 0.50,
            '硅光模块': 0.30,
        }
        return defaults.get(prod_name, 0.10)
    
    def _default_asp_change(self, prod_name: str) -> float:
        """默认ASP变化"""
        defaults = {
            '800G/1.6T高速光模块': 0.05,
            '400G光模块': -0.05,
            '200G光模块': -0.05,
            '400G/200G光模块': -0.05,
            '100G及以下光模块': -0.10,
            'NPO/CPO': 0.10,
            '硅光模块': 0.05,
        }
        return defaults.get(prod_name, -0.05)
    
    def _supplement_product_data(self, prod_name: str, pl: ProductLine):
        """补搜缺失的产品数据"""
        query = f"{prod_name} 2025 2026 出货量 出货增长 出货量预测"
        items = self._search_exa(query, 3, 15)
        
        text = " ".join([i.get('full_text', '') for i in items])
        growth = self._extract_growth(text)
        if growth is not None:
            pl.industry_shipment_growth = growth
            pl.search_evidence.append(f"补搜出货增长{growth:+.1%}")
        
        asp = self._extract_asp_change(text)
        if asp != 0.0:
            pl.asp_change = asp
            pl.search_evidence.append(f"补搜ASP{asp:+.1%}")
    
    def _search_company_market_share(self, products: Dict[str, ProductLine], all_text: str):
        """搜索公司市占率（一次搜索）"""
        # 先从已有文本中提取
        share = self._extract_market_share(all_text, self.stock_name)
        
        if share is None:
            # 补搜
            query = f"{self.stock_name} 光模块 市占率 市场份额 排名"
            items = self._search_exa(query, 3, 15)
            text = " ".join([i.get('full_text', '') for i in items])
            share = self._extract_market_share(text, self.stock_name)
        
        # 分配市占率到各产品
        for prod_name, pl in products.items():
            if share is not None:
                pl.company_market_share = share
                pl.search_evidence.append(f"市占率{share:.1%}")
            else:
                # 默认市占率
                pl.company_market_share = self._default_market_share(prod_name)
                pl.search_evidence.append(f"默认市占率{pl.company_market_share:.1%}")
    
    def _default_market_share(self, prod_name: str) -> float:
        """默认市占率"""
        defaults = {
            '800G/1.6T高速光模块': 0.40,
            '400G光模块': 0.30,
            '200G光模块': 0.25,
            '400G/200G光模块': 0.30,
            '100G及以下光模块': 0.15,
            'NPO/CPO': 0.25,
            '硅光模块': 0.20,
        }
        return defaults.get(prod_name, 0.20)
    
    def _create_default_products(self, segment: BusinessSegment) -> Dict[str, ProductLine]:
        """创建默认产品列表"""
        products = {}
        if '光模块' in segment.name or '光通讯' in segment.name:
            for prod in ['800G/1.6T高速光模块', '400G/200G光模块', '100G及以下光模块']:
                pl = ProductLine(name=prod, parent_segment='')
                pl.industry_shipment_growth = self._default_growth(prod)
                pl.asp_change = self._default_asp_change(prod)
                pl.company_market_share = self._default_market_share(prod)
                pl.search_evidence.append("默认数据（搜索无结果）")
                products[prod] = pl
        else:
            pl = ProductLine(name=segment.name, parent_segment='')
            pl.industry_shipment_growth = 0.10
            pl.asp_change = 0.0
            pl.company_market_share = 0.10
            pl.search_evidence.append("默认数据")
            products[segment.name] = pl
        return products
    
    # ========== 预测计算 ==========
    
    def allocate_revenue(self, segment: BusinessSegment, products: Dict[str, ProductLine]):
        """按ASP权重分配营收"""
        asp_weights = {
            '800G/1.6T': 8.0, '1.6T': 8.0, '800G': 8.0,
            '400G': 3.0, '200G': 1.5,
            '100G': 1.0, '50G': 0.5, '25G': 0.3,
            'NPO': 10.0, 'CPO': 10.0,
            '硅光': 6.0, 'silicon': 6.0,
        }
        
        weights = []
        for prod_name in products.keys():
            w = 1.0
            for key, val in asp_weights.items():
                if key in prod_name:
                    w = val
                    break
            weights.append(w)
        
        total_weight = sum(weights)
        
        for i, (prod_name, pl) in enumerate(products.items()):
            weight_pct = weights[i] / total_weight
            pl.revenue_base = segment.revenue * weight_pct
            pl.profit_base = segment.profit * weight_pct
            pl.margin = pl.profit_base / pl.revenue_base if pl.revenue_base > 0 else segment.margin
        
        return products
    
    def forecast_product(self, pl: ProductLine) -> ProductLine:
        """预测单个产品"""
        print(f"\n📈 预测 [{pl.name}]...")
        
        revenue_factor = (1 + pl.industry_shipment_growth) * (1 + pl.asp_change)
        pl.revenue_forecast = pl.revenue_base * revenue_factor
        
        scale_effect = min(0.02, max(-0.02, pl.industry_shipment_growth * 0.05))
        forecast_margin = pl.margin + scale_effect
        forecast_margin = max(0.05, min(0.60, forecast_margin))
        pl.profit_forecast = pl.revenue_forecast * forecast_margin
        
        print(f"   基期: 营收 {pl.revenue_base:.2f}亿 | 利润 {pl.profit_base:.2f}亿 | 利润率 {pl.margin:.1%}")
        print(f"   出货增长: {pl.industry_shipment_growth:+.1%} | ASP: {pl.asp_change:+.1%}")
        print(f"   因子: {revenue_factor:.2f} → 预测营收 {pl.revenue_forecast:.2f}亿 | 利润 {pl.profit_forecast:.2f}亿")
        
        return pl
    
    def forecast_segment(self, segment: BusinessSegment) -> BusinessSegment:
        """预测业务线"""
        print(f"\n{'='*75}")
        print(f"业务线预测: [{segment.name}]")
        print(f"{'='*75}")
        
        # 批量搜索行业数据
        products = self.search_industry_batch(segment)
        
        # 分配营收
        self.allocate_revenue(segment, products)
        
        # 预测每个产品
        total_forecast_revenue = 0.0
        total_forecast_profit = 0.0
        product_lines = []
        
        for prod_name, pl in products.items():
            self.forecast_product(pl)
            product_lines.append(pl)
            total_forecast_revenue += pl.revenue_forecast
            total_forecast_profit += pl.profit_forecast
        
        segment.product_lines = product_lines
        segment.forecast_revenue = total_forecast_revenue
        segment.forecast_profit = total_forecast_profit
        
        # 汇总输出
        print(f"\n📋 [{segment.name}] 汇总:")
        print(f"{'产品':<25} {'基期营收':>10} {'预测营收':>10} {'变化':>8} {'基期利润':>10} {'预测利润':>10} {'变化':>8}")
        print(f"{'─'*85}")
        for pl in product_lines:
            rev_chg = (pl.revenue_forecast - pl.revenue_base) / pl.revenue_base if pl.revenue_base > 0 else 0
            prof_chg = (pl.profit_forecast - pl.profit_base) / pl.profit_base if pl.profit_base > 0 else 0
            print(f"{pl.name:<25} {pl.revenue_base:>10.2f} {pl.revenue_forecast:>10.2f} {rev_chg:>+7.1%} {pl.profit_base:>10.2f} {pl.profit_forecast:>10.2f} {prof_chg:>+7.1%}")
        print(f"{'─'*85}")
        rev_chg = (segment.forecast_revenue - segment.revenue) / segment.revenue
        prof_chg = (segment.forecast_profit - segment.profit) / segment.profit
        print(f"{'合计':<25} {segment.revenue:>10.2f} {segment.forecast_revenue:>10.2f} {rev_chg:>+7.1%} {segment.profit:>10.2f} {segment.forecast_profit:>10.2f} {prof_chg:>+7.1%}")
        
        return segment
    
    def run_forecast(self) -> Dict:
        """执行完整流程"""
        self.fetch_business_segments()
        if not self.segments:
            return {}
        
        for segment in self.segments:
            self.forecast_segment(segment)
            time.sleep(0.5)
        
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
        lines.append(f"# {self.stock_name} ({self.stock_code}) 业务线拆分估值分析")
        lines.append(f"\n> **分析日期**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"> **基准报告期**: {self.report_period}")
        lines.append(f"> **方法**: 先搜主要产品 → 批量搜行业量价 → 预测汇总")
        lines.append("")
        
        for seg in self.segments:
            lines.append(f"## {seg.name}")
            lines.append("")
            lines.append(f"- **基期营收**: {seg.revenue:.2f}亿 (占比{seg.revenue_pct:.1%})")
            lines.append("")
            
            if seg.product_lines:
                lines.append("**细分产品预测**:")
                lines.append("")
                lines.append("| 产品 | 出货增长 | ASP变化 | 市占率 | 基期营收 | 预测营收 | 变化 | 来源 |")
                lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|")
                for pl in seg.product_lines:
                    rev_chg = (pl.revenue_forecast - pl.revenue_base) / pl.revenue_base if pl.revenue_base > 0 else 0
                    sources = ', '.join(pl.data_sources[:1])
                    evidence = ' | '.join(pl.search_evidence[:2])
                    lines.append(f"| {pl.name} | {pl.industry_shipment_growth:+.1%} | {pl.asp_change:+.1%} | {pl.company_market_share:.1%} | {pl.revenue_base:.2f}亿 | {pl.revenue_forecast:.2f}亿 | {rev_chg:+.1%} | {evidence} |")
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
        lines.append("1. **市占率不变**: 假设公司各产品市占率维持基期水平")
        lines.append("2. **数据来源**: Exa AI搜索 (LightCounting/Yole/券商研报)")
        lines.append("3. **原料成本不变**: 已内含在利润率中")
        lines.append("")
        
        return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='业务线拆分估值分析器 v3.1')
    parser.add_argument('code', help='股票代码')
    parser.add_argument('--name', '-n', default='', help='股票名称')
    parser.add_argument('--output', '-o', default='', help='输出路径')
    args = parser.parse_args()
    
    forecaster = OptimizedForecaster()
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
