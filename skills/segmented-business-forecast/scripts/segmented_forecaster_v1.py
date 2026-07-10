#!/root/.openclaw/workspace/venv/bin/python3
"""
业务线拆分估值分析器 v1.0
按业务/产品逐个拆解，分别预测，最后汇总

核心流程:
1. fina_mainbz 获取最新财报的业务拆分数据
2. 多源搜索每个业务线的市场动态(价格/出货/需求)
3. 分业务估算营收变化率
4. 假设原料成本不变，只调整管理/营销费用
5. 汇总计算总利润
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

# 加载环境变量
sys.path.insert(0, '/root/.openclaw/workspace')
sys.path.insert(0, '/root/.openclaw/workspace/tools')

import tushare as ts


@dataclass
class BusinessSegment:
    """业务线数据"""
    name: str                   # 业务/产品名称
    revenue: float             # 收入（亿元）
    profit: float              # 利润（亿元）
    revenue_pct: float         # 收入占比
    profit_pct: float          # 利润占比
    margin: float              # 毛利率
    
    # 预测字段
    price_change: float = 0.0  # 价格变化率(+0.15 = +15%)
    volume_change: float = 0.0 # 出货量变化率
    mgmt_cost_change: float = 0.05  # 管理/营销成本变化率(默认+5%)
    
    # 预测结果
    forecast_revenue: float = 0.0
    forecast_profit: float = 0.0


class SegmentedBusinessForecaster:
    """业务线拆分估值分析器"""
    
    def __init__(self, tushare_token: Optional[str] = None):
        if tushare_token:
            self.pro = ts.pro_api(tushare_token)
        else:
            # 尝试从环境变量或本地获取
            token = os.environ.get('TUSHARE_TOKEN')
            if not token:
                # 尝试读取 .env
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
        self.report_period: str = ""  # 最新报告期
        self.total_revenue: float = 0.0
        self.total_profit: float = 0.0
    
    def load_stock(self, code: str, name: str = ""):
        """加载股票基本信息"""
        self.stock_code = code
        self.stock_name = name
        print(f"\n{'='*60}")
        print(f"业务线拆分估值分析: {name} ({code})")
        print(f"{'='*60}")
    
    def fetch_business_segments(self) -> List[BusinessSegment]:
        """
        从 fina_mainbz 获取分业务数据
        type='P' 按产品, type='D' 按地区
        """
        print("\n📊 Step 1: 获取分业务/产品财报数据...")
        
        # 确定最新报告期
        year = datetime.now().year
        
        # 尝试获取最近3年的年报/半年报数据
        periods = []
        for y in range(year, year-3, -1):
            periods.extend([f"{y}1231", f"{y}0630"])
        
        best_df = None
        best_period = None
        
        for period in periods:
            try:
                df = self.pro.fina_mainbz(
                    ts_code=self.stock_code,
                    period=period,
                    type='P'  # 按产品
                )
                if df is not None and len(df) > 0:
                    best_df = df
                    best_period = period
                    break
            except Exception as e:
                continue
        
        if best_df is None or len(best_df) == 0:
            print(f"   ⚠️ 无法获取 {self.stock_code} 的分业务数据")
            return []
        
        self.report_period = best_period
        print(f"   ✅ 获取到 {best_period} 数据, 共{len(best_df)}个业务/产品线")
        
        # 解析数据
        segments = []
        total_rev = 0.0
        total_prof = 0.0
        
        for _, row in best_df.iterrows():
            name = str(row.get('bz_item', '')).strip()
            sales = float(row.get('bz_sales', 0)) / 1e8  # 转为亿元
            profit = float(row.get('bz_profit', 0)) / 1e8
            
            if sales <= 0:
                continue
                
            total_rev += sales
            total_prof += profit
            
            segments.append(BusinessSegment(
                name=name,
                revenue=sales,
                profit=profit,
                revenue_pct=0.0,  # 稍后计算
                profit_pct=0.0,
                margin=profit / sales if sales > 0 else 0
            ))
        
        # 计算占比
        for seg in segments:
            seg.revenue_pct = seg.revenue / total_rev if total_rev > 0 else 0
            seg.profit_pct = seg.profit / total_prof if total_prof != 0 else 0
        
        # 按收入占比排序
        segments.sort(key=lambda x: x.revenue_pct, reverse=True)
        
        self.total_revenue = total_rev
        self.total_profit = total_prof
        self.segments = segments
        
        print(f"\n   总营收: {total_rev:.2f}亿 | 总利润: {total_prof:.2f}亿")
        print(f"   业务线数量: {len(segments)}")
        
        return segments
    
    def display_segments(self):
        """展示业务拆分结果"""
        print(f"\n{'─'*60}")
        print(f"{'业务/产品线':<20} {'收入(亿)':>10} {'占比':>8} {'利润(亿)':>10} {'利润率':>8}")
        print(f"{'─'*60}")
        
        for seg in self.segments:
            print(f"{seg.name:<20} {seg.revenue:>10.2f} {seg.revenue_pct:>7.1%} {seg.profit:>10.2f} {seg.margin:>7.1%}")
        
        print(f"{'─'*60}")
        print(f"{'合计':<20} {self.total_revenue:>10.2f} {'100.0%':>8} {self.total_profit:>10.2f}")
        print(f"{'─'*60}")
    
    def search_business_dynamics(self, segment: BusinessSegment) -> Dict:
        """
        多源搜索单个业务线的市场动态
        返回: {price_trend, volume_trend, demand_trend, news_count, sources}
        """
        print(f"\n🔍 Step 2: 搜索 [{segment.name}] 市场动态...")
        
        search_keywords = [
            f"{self.stock_name} {segment.name}",
            f"{segment.name} 价格 涨价 降价",
            f"{segment.name} 出货量 订单",
            f"{segment.name} 需求 市场",
        ]
        
        results = {
            'price_trend': 'unknown',
            'volume_trend': 'unknown', 
            'demand_trend': 'unknown',
            'price_change_est': 0.0,
            'volume_change_est': 0.0,
            'news_items': [],
            'sources': []
        }
        
        # P1: Exa搜索
        try:
            query = f"{self.stock_name} {segment.name} 价格 订单 出货 2025 2026"
            exa_result = self._search_exa(query)
            if exa_result:
                results['sources'].append('Exa')
                results['news_items'].extend(exa_result.get('items', [])[:3])
        except Exception as e:
            print(f"   Exa搜索失败: {e}")
        
        # P2: 知识星球搜索 (如果可用)
        try:
            zsxq_result = self._search_zsxq(f"{self.stock_name} {segment.name}")
            if zsxq_result:
                results['sources'].append('知识星球')
                results['news_items'].extend(zsxq_result[:2])
        except Exception as e:
            pass  # 知识星球不是必须
        
        # P3: 新浪财经
        try:
            sina_result = self._search_sina(f"{self.stock_name} {segment.name}")
            if sina_result:
                results['sources'].append('新浪财经')
                results['news_items'].extend(sina_result[:2])
        except Exception as e:
            pass
        
        # 分析搜索结果，估算趋势
        self._analyze_trends(results, segment)
        
        print(f"   价格趋势: {results['price_trend']} (估: {results['price_change_est']:+.1%})")
        print(f"   出货趋势: {results['volume_trend']} (估: {results['volume_change_est']:+.1%})")
        print(f"   数据来源: {', '.join(results['sources'])}")
        
        return results
    
    def _search_exa(self, query: str, num_results: int = 5) -> Optional[Dict]:
        """Exa搜索 - 解析纯文本输出"""
        try:
            result = subprocess.run(
                ['mcporter', 'call', 'exa.web_search_exa',
                 f'query={query}', f'numResults={num_results}'],
                capture_output=True, text=True, timeout=30
            )
            output = result.stdout
            
            # 解析纯文本格式: Title/URL/Published/Author/Highlights
            items = []
            current = {}
            lines = output.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.startswith('Title:'):
                    if current:
                        items.append(current)
                    current = {'title': line[6:].strip()}
                elif line.startswith('URL:'):
                    current['url'] = line[4:].strip()
                elif line.startswith('Highlights:'):
                    current['highlights'] = ''
                elif line and current and 'highlights' in current and not line.startswith('---'):
                    current['highlights'] += ' ' + line
            
            if current:
                items.append(current)
            
            # 合并title和highlights作为content
            for item in items:
                item['content'] = item.get('title', '') + ' ' + item.get('highlights', '')
            
            return {'items': items} if items else None
            
        except Exception as e:
            print(f"   Exa搜索异常: {e}")
            return None
    
    def _search_zsxq(self, keyword: str) -> List[Dict]:
        """知识星球搜索"""
        try:
            sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/scripts')
            from multi_source_news_v2 import ZsxqSearcher
            searcher = ZsxqSearcher()
            results = searcher.search(keyword, count=5)
            return results
        except Exception as e:
            return []
    
    def _search_sina(self, keyword: str) -> List[Dict]:
        """新浪财经搜索"""
        try:
            url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&num=10&keywords={keyword}"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            items = []
            if data.get('result') and data['result'].get('data'):
                for item in data['result']['data'][:5]:
                    items.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'time': item.get('time', '')
                    })
            return items
        except Exception as e:
            return []
    
    def _analyze_trends(self, results: Dict, segment: BusinessSegment):
        """基于搜索结果分析趋势 - 扩展信号词库"""
        all_text = " ".join([str(n.get('title', '')) + ' ' + str(n.get('content', '')) for n in results['news_items']])
        all_text = all_text.lower()
        
        # 价格趋势分析 - 扩展信号词
        price_up_signals = [
            '涨价', '价格上涨', '提价', '涨价潮', '涨价预期', '涨价函', 'price increase',
            '价格稳中有升', '毛利率提升', '毛利率上升', '毛利率有望', '涨价落地',
            '产品提价', '售价上涨', ' ASP提升', '均价上涨'
        ]
        price_down_signals = [
            '降价', '价格下跌', '降价促销', '价格战', 'price cut', '降价潮',
            '价格承压', '毛利率下滑', '毛利率下降', '产品降价', '售价下降',
            ' ASP下降', '均价下跌', '价格竞争'
        ]
        
        up_count = sum(1 for s in price_up_signals if s in all_text)
        down_count = sum(1 for s in price_down_signals if s in all_text)
        
        if up_count > down_count and up_count > 0:
            results['price_trend'] = 'up'
            results['price_change_est'] = 0.05 + 0.03 * up_count
        elif down_count > up_count and down_count > 0:
            results['price_trend'] = 'down'
            results['price_change_est'] = -0.05 - 0.03 * down_count
        else:
            results['price_trend'] = 'stable'
            results['price_change_est'] = 0.0
        
        # 出货量/需求趋势分析 - 大幅扩展信号词
        vol_up_signals = [
            '订单增长', '出货量增长', '产能满产', '供不应求', '订单饱满', '订单排期', '扩产',
            '需求旺盛', '需求强劲', '需求增长', '订单增加', '出货增加', '持续增加',
            '加单', '催货', '追加订单', '订单超预期', '订单饱满', '产能利用率',
            '满产', '产能紧张', '扩产计划', '产能扩张', '出货量提升',
            '销售增长', '销量增长', '销量提升', '订单充足', '订单满载',
            '客户加单', '客户追单', '订单持续', '出货持续', '增长强劲'
        ]
        vol_down_signals = [
            '订单下滑', '出货量下降', '产能过剩', '需求疲软', '库存积压', '砍单',
            '需求下降', '需求减弱', '订单减少', '出货减少', '持续减少',
            '订单取消', '推迟发货', '延迟交付', '需求放缓', '需求不振',
            '库存高企', '库存压力', '去化缓慢', '销售下滑', '销量下降',
            '订单不足', '产能闲置', '开工率下降', '出货量下滑'
        ]
        
        vol_up = sum(1 for s in vol_up_signals if s in all_text)
        vol_down = sum(1 for s in vol_down_signals if s in all_text)
        
        if vol_up > vol_down and vol_up > 0:
            results['volume_trend'] = 'up'
            results['volume_change_est'] = 0.10 + 0.05 * vol_up
        elif vol_down > vol_up and vol_down > 0:
            results['volume_trend'] = 'down'
            results['volume_change_est'] = -0.10 - 0.05 * vol_down
        else:
            results['volume_trend'] = 'stable'
            results['volume_change_est'] = 0.0
        
        # 限制变化幅度
        results['price_change_est'] = max(-0.30, min(0.30, results['price_change_est']))
        results['volume_change_est'] = max(-0.50, min(0.80, results['volume_change_est']))
    
    def forecast_segment(self, segment: BusinessSegment, dynamics: Dict) -> BusinessSegment:
        """
        预测单个业务线的营收和利润
        
        公式:
        预测营收 = 基期营收 × (1 + 价格变化) × (1 + 出货量变化)
        预测利润 = 预测营收 × 基期利润率 × (1 - 管理营销成本变化)
        
        假设:
        - 原料成本不变（已含在利润率中）
        - 管理/营销成本按比例变化
        """
        print(f"\n📈 Step 3: 预测 [{segment.name}]...")
        
        # 营收预测
        price_factor = 1 + dynamics['price_change_est']
        volume_factor = 1 + dynamics['volume_change_est']
        
        segment.price_change = dynamics['price_change_est']
        segment.volume_change = dynamics['volume_change_est']
        
        segment.forecast_revenue = segment.revenue * price_factor * volume_factor
        
        # 利润预测
        # 假设原料成本不变，利润率变化主要来自管理/营销费用变化
        # 简单模型: 利润 = 营收 × 利润率 × (1 - 费用率变化)
        # 更精确: 固定费用(管理/营销)变化，变动费用(原料)不变
        
        # 基期利润率
        base_margin = segment.margin if segment.margin > 0 else 0.05
        
        # 假设管理/营销费用占营收的10-15%，这部分可能变化
        # 营收增长时，规模效应可能降低费用率；竞争激烈时费用率上升
        mgmt_cost_factor = 1 + segment.mgmt_cost_change
        
        # 利润 = 营收 - 原料成本(不变比例) - 管理营销费用(变化)
        # 简化: 预测利润 = 预测营收 × (利润率 - 费用率变化调整)
        margin_adjustment = -0.02 * (mgmt_cost_factor - 1)  # 费用每增1%，利润率降2%
        forecast_margin = base_margin + margin_adjustment
        forecast_margin = max(0.01, min(0.60, forecast_margin))  # 限制在1%-60%
        
        segment.forecast_profit = segment.forecast_revenue * forecast_margin
        
        print(f"   基期营收: {segment.revenue:.2f}亿")
        print(f"   价格变化: {segment.price_change:+.1%} | 出货变化: {segment.volume_change:+.1%}")
        print(f"   预测营收: {segment.forecast_revenue:.2f}亿 (×{price_factor*volume_factor:.2f})")
        print(f"   基期利润率: {base_margin:.1%} | 预测利润率: {forecast_margin:.1%}")
        print(f"   预测利润: {segment.forecast_profit:.2f}亿")
        
        return segment
    
    def run_forecast(self) -> Dict:
        """
        执行完整预测流程
        """
        # Step 1: 获取业务拆分
        self.fetch_business_segments()
        if not self.segments:
            print("\n❌ 无法获取业务拆分数据，分析终止")
            return {}
        
        self.display_segments()
        
        # Step 2-3: 逐业务搜索+预测
        for segment in self.segments:
            dynamics = self.search_business_dynamics(segment)
            self.forecast_segment(segment, dynamics)
            time.sleep(1)  # 避免请求过频
        
        # Step 4: 汇总
        return self.summarize()
    
    def summarize(self) -> Dict:
        """汇总预测结果"""
        print(f"\n{'='*60}")
        print("汇总预测结果")
        print(f"{'='*60}")
        
        total_forecast_revenue = sum(s.forecast_revenue for s in self.segments)
        total_forecast_profit = sum(s.forecast_profit for s in self.segments)
        
        revenue_change = (total_forecast_revenue - self.total_revenue) / self.total_revenue if self.total_revenue > 0 else 0
        profit_change = (total_forecast_profit - self.total_profit) / self.total_profit if self.total_profit != 0 else 0
        
        print(f"\n{'业务/产品线':<20} {'基期营收':>10} {'预测营收':>10} {'变化':>8} {'基期利润':>10} {'预测利润':>10} {'变化':>8}")
        print(f"{'─'*80}")
        
        for seg in self.segments:
            rev_chg = (seg.forecast_revenue - seg.revenue) / seg.revenue if seg.revenue > 0 else 0
            prof_chg = (seg.forecast_profit - seg.profit) / seg.profit if seg.profit != 0 else 0
            print(f"{seg.name:<20} {seg.revenue:>10.2f} {seg.forecast_revenue:>10.2f} {rev_chg:>+7.1%} {seg.profit:>10.2f} {seg.forecast_profit:>10.2f} {prof_chg:>+7.1%}")
        
        print(f"{'─'*80}")
        print(f"{'合计':<20} {self.total_revenue:>10.2f} {total_forecast_revenue:>10.2f} {revenue_change:>+7.1%} {self.total_profit:>10.2f} {total_forecast_profit:>10.2f} {profit_change:>+7.1%}")
        print(f"{'='*60}")
        
        result = {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'report_period': self.report_period,
            'base_revenue': self.total_revenue,
            'base_profit': self.total_profit,
            'forecast_revenue': total_forecast_revenue,
            'forecast_profit': total_forecast_profit,
            'revenue_change': revenue_change,
            'profit_change': profit_change,
            'segments': []
        }
        
        for seg in self.segments:
            result['segments'].append({
                'name': seg.name,
                'base_revenue': seg.revenue,
                'base_profit': seg.profit,
                'base_margin': seg.margin,
                'price_change': seg.price_change,
                'volume_change': seg.volume_change,
                'forecast_revenue': seg.forecast_revenue,
                'forecast_profit': seg.forecast_profit,
                'forecast_margin': seg.forecast_profit / seg.forecast_revenue if seg.forecast_revenue > 0 else 0
            })
        
        return result
    
    def generate_report(self) -> str:
        """生成Markdown格式的分析报告"""
        result = self.summarize()
        if not result:
            return "无法生成报告：没有数据"
        
        lines = []
        lines.append(f"# {self.stock_name} ({self.stock_code}) 业务线拆分估值分析")
        lines.append(f"\n> **分析日期**: {datetime.now().strftime('%Y-%m-%d')}")
        lines.append(f"> **基准报告期**: {self.report_period}")
        lines.append(f"> **方法**: 业务线拆分预测 + 多源信息验证")
        lines.append("")
        
        lines.append("## 一、业务拆分概览")
        lines.append("")
        lines.append("| 业务/产品线 | 收入(亿) | 占比 | 利润(亿) | 利润率 |")
        lines.append("|:---|---:|---:|---:|---:|")
        for seg in self.segments:
            lines.append(f"| {seg.name} | {seg.revenue:.2f} | {seg.revenue_pct:.1%} | {seg.profit:.2f} | {seg.margin:.1%} |")
        lines.append(f"| **合计** | **{self.total_revenue:.2f}** | **100%** | **{self.total_profit:.2f}** | - |")
        lines.append("")
        
        lines.append("## 二、分业务预测")
        lines.append("")
        
        for seg in self.segments:
            lines.append(f"### {seg.name}")
            lines.append("")
            lines.append(f"- **基期营收**: {seg.revenue:.2f}亿 (占比{seg.revenue_pct:.1%})")
            lines.append(f"- **基期利润**: {seg.profit:.2f}亿 (利润率{seg.margin:.1%})")
            lines.append("")
            lines.append("**市场动态假设**:")
            lines.append(f"- 价格变化: {seg.price_change:+.1%}")
            lines.append(f"- 出货量变化: {seg.volume_change:+.1%}")
            lines.append(f"- 管理/营销成本变化: {seg.mgmt_cost_change:+.1%}")
            lines.append("")
            lines.append("**预测结果**:")
            lines.append(f"- 预测营收: {seg.forecast_revenue:.2f}亿")
            lines.append(f"- 预测利润: {seg.forecast_profit:.2f}亿")
            lines.append(f"- 预测利润率: {seg.forecast_profit/seg.forecast_revenue:.1%}" if seg.forecast_revenue > 0 else "")
            lines.append("")
        
        lines.append("## 三、汇总预测")
        lines.append("")
        lines.append("| 指标 | 基期 | 预测 | 变化 |")
        lines.append("|:---|---:|---:|---:|")
        lines.append(f"| 总营收 | {result['base_revenue']:.2f}亿 | {result['forecast_revenue']:.2f}亿 | {result['revenue_change']:+.1%} |")
        lines.append(f"| 总利润 | {result['base_profit']:.2f}亿 | {result['forecast_profit']:.2f}亿 | {result['profit_change']:+.1%} |")
        lines.append("")
        
        lines.append("## 四、关键假设")
        lines.append("")
        lines.append("1. **原料成本不变**: 假设各业务线的原材料成本结构不变")
        lines.append("2. **管理/营销成本**: 按比例变化（默认+5%）")
        lines.append("3. **价格/出货变化**: 基于多源信息搜索（Exa/新浪/知识星球）的定性判断")
        lines.append("4. **规模效应**: 营收增长时假设费用率小幅下降")
        lines.append("")
        
        lines.append("## 五、风险提示")
        lines.append("")
        lines.append("- ⚠️ 多源搜索结果可能存在偏差，价格/出货变化率为估算值")
        lines.append("- ⚠️ 未考虑突发政策、技术替代、供应链中断等黑天鹅事件")
        lines.append("- ⚠️ 管理/营销成本假设为简化模型，实际情况可能更复杂")
        lines.append("")
        
        return "\n".join(lines)


# 保留导入requests（在类定义后）
import requests


def main():
    """命令行入口"""
    import argparse
    parser = argparse.ArgumentParser(description='业务线拆分估值分析器')
    parser.add_argument('code', help='股票代码 (如 300308.SZ)')
    parser.add_argument('--name', '-n', default='', help='股票名称')
    parser.add_argument('--output', '-o', default='', help='输出报告路径')
    args = parser.parse_args()
    
    forecaster = SegmentedBusinessForecaster()
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
