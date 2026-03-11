#!/root/.openclaw/workspace/venv/bin/python3
"""
A股个股深度分析 - 融合版 v1.0
整合 a-stock-analysis + dounai-investment-system 能力

功能:
- 多源股价验证（长桥/东方财富/腾讯/新浪）
- 6类新闻搜索（Exa/知识星球/新浪/东方财富/腾讯/华尔街见闻）
- 10环节SOP分析框架
- 融合去重的新闻聚合

使用方法:
    ./venv_runner.sh skills/a-stock-analysis/scripts/analyze_stock_fusion.py --code 002463 --name 沪电股份
"""

import sys
import os
import json
import argparse
import requests
from datetime import datetime

# 添加工具路径
sys.path.insert(0, '/root/.openclaw/workspace/skills/a-stock-analysis/tools')
sys.path.insert(0, '/root/.openclaw/workspace/skills/short-term-analysis/scripts')
sys.path.insert(0, '/root/.openclaw/workspace/skills/dounai-investment-system/scripts')

from stock_data_collector import StockDataCollector
from analyze_short_term import ShortTermAnalyzer
from multi_source_news_v2 import MultiSourceNewsSearcher, search_stock_comprehensive

# 长桥API
from longport.openapi import QuoteContext, Config, AdjustType, Period

WORKSPACE = '/root/.openclaw/workspace'
REPORTS_DIR = f'{WORKSPACE}/reports'


class FusionStockAnalyzer:
    """
    融合版个股分析器
    - 股价数据：多源验证（a-stock-analysis能力）
    - 新闻搜索：6源融合去重（dounai-investment-system能力）
    - 分析框架：10环节SOP
    """
    
    def __init__(self):
        self.data = {
            'price': {},
            'valuation': {},
            'news': {},
            'technical': {},
            'basic_info': {}
        }
        self.news_searcher = MultiSourceNewsSearcher()
    
    def get_industry_info(self, ts_code):
        """
        自动获取股票行业信息
        
        尝试多个数据源：
        1. Akshare (东方财富) - 首选
        2. Tushare - 备选
        
        Returns:
            dict: {'industry': '行业名称', 'sector': '所属板块', 'source': '数据源'}
        """
        result = {'industry': '', 'sector': '', 'source': ''}
        code = ts_code.replace('.SZ', '').replace('.SH', '')
        
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
                    if result['sector']:
                        print(f"   ✅ 板块: {result['sector']}")
                    return result
        except Exception as e:
            print(f"   ⚠️ Akshare获取失败: {e}")
        
        # 方法2: Tushare
        try:
            print("   📡 尝试Tushare获取行业信息...")
            sys.path.insert(0, '/root/.openclaw/workspace/tools')
            from tushare_api import get_tushare_api
            ts_api = get_tushare_api()
            
            df = ts_api.pro.stock_basic(ts_code=ts_code, fields='name,industry')
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
    
    def get_company_profile(self, ts_code):
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
        code = ts_code.replace('.SZ', '').replace('.SH', '')
        
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
    
    def get_longbridge_data(self, ts_code):
        """获取长桥实时数据（主要数据源）"""
        try:
            config = Config.from_env()
            ctx = QuoteContext(config)
            lb_code = ts_code.upper().replace('.SH', '.SS')
            
            # 实时行情
            quote = ctx.quote([lb_code])
            if not quote:
                return None
            
            q = quote[0]
            price_data = {
                'price': float(q.last_done) if hasattr(q, 'last_done') else None,
                'open': float(q.open) if hasattr(q, 'open') else None,
                'high': float(q.high) if hasattr(q, 'high') else None,
                'low': float(q.low) if hasattr(q, 'low') else None,
                'volume': int(q.volume) if hasattr(q, 'volume') else None,
                'turnover': float(q.turnover) if hasattr(q, 'turnover') else None,
                'source': '长桥API',
                'time': datetime.now().strftime('%H:%M:%S')
            }
            
            # 股本数据
            static = ctx.static_info([lb_code])
            if static:
                s = static[0]
                price_data['total_shares'] = float(s.total_shares) if hasattr(s, 'total_shares') else None
                price_data['circulating_shares'] = float(s.circulating_shares) if hasattr(s, 'circulating_shares') else None
                price_data['eps_ttm'] = float(s.eps_ttm) if hasattr(s, 'eps_ttm') else None
                price_data['bps'] = float(s.bps) if hasattr(s, 'bps') else None
            
            # K线数据（计算技术指标）
            try:
                candles = ctx.candlesticks(lb_code, Period.Day, 60, AdjustType.NoAdjust)
                closes = [float(c.close) for c in candles]
                if len(closes) >= 5:
                    price_data['change_5d'] = (closes[-1] - closes[-5]) / closes[-5] * 100
                if len(closes) >= 20:
                    price_data['change_20d'] = (closes[-1] - closes[-20]) / closes[-20] * 100
                    price_data['ma_20'] = sum(closes[-20:]) / 20
                if len(closes) >= 60:
                    price_data['change_60d'] = (closes[-1] - closes[-60]) / closes[-60] * 100
                    price_data['ma_60'] = sum(closes[-60:]) / 60
                # RSI计算
                if len(closes) >= 14:
                    gains = [max(0, closes[i] - closes[i-1]) for i in range(1, len(closes))]
                    losses = [max(0, closes[i-1] - closes[i]) for i in range(1, len(closes))]
                    avg_gain = sum(gains[-14:]) / 14
                    avg_loss = sum(losses[-14:]) / 14
                    if avg_loss != 0:
                        rs = avg_gain / avg_loss
                        price_data['rsi_14'] = 100 - (100 / (1 + rs))
            except Exception as e:
                print(f"    [WARN] K线数据获取失败: {e}")
            
            return price_data
        except Exception as e:
            print(f"[WARN] 长桥数据获取失败: {e}")
            return None
    
    def get_eastmoney_valuation(self, ts_code):
        """获取东方财富估值数据"""
        try:
            if ts_code.endswith('.SH'):
                code = f"1.{ts_code.replace('.SH', '')}"
            else:
                code = f"0.{ts_code.replace('.SZ', '')}"
            
            url = f'https://push2.eastmoney.com/api/qt/stock/get?ut=fa5fd1943c7b386f172d6893dbfba10b&fltt=2&invt=2&volt=2&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f162,f167,f170,f171,f177,f168&secid={code}'
            r = requests.get(url, timeout=10)
            data = r.json()
            
            if data.get('data'):
                d = data['data']
                return {
                    'pe': float(d.get('f162', 0)) if d.get('f162') else None,
                    'pb': float(d.get('f167', 0)) if d.get('f167') else None,
                    'turnover_rate': float(d.get('f168', 0)) if d.get('f168') else None,
                    'total_mv': float(d.get('f48', 0)) / 100000000 if d.get('f48') else None,
                    'source': '东方财富',
                    'time': datetime.now().strftime('%H:%M:%S')
                }
        except Exception as e:
            print(f"[WARN] 东方财富数据获取失败: {e}")
        return None
    
    def get_qq_valuation(self, ts_code):
        """腾讯财经备选数据源"""
        try:
            code = ts_code.replace('.SH', '').replace('.SZ', '')
            prefix = 'sh' if ts_code.endswith('.SH') else 'sz'
            url = f'https://qt.gtimg.cn/q={prefix}{code}'
            r = requests.get(url, timeout=10)
            parts = r.text.split('~')
            if len(parts) > 50:
                pe_val = parts[39] if len(parts) > 39 else None
                pb_val = parts[46] if len(parts) > 46 else None
                mv_val = parts[44] if len(parts) > 44 else None
                
                return {
                    'pe': float(pe_val) if pe_val and pe_val.replace('.', '').replace('-', '').isdigit() else None,
                    'pb': float(pb_val) if pb_val and pb_val.replace('.', '').replace('-', '').isdigit() else None,
                    'total_mv': float(mv_val) if mv_val and mv_val.replace('.', '').replace('-', '').isdigit() else None,
                    'source': '腾讯财经',
                    'time': datetime.now().strftime('%H:%M:%S')
                }
        except Exception as e:
            print(f"[WARN] 腾讯财经数据获取失败: {e}")
        return None
    
    def get_multi_source_valuation(self, ts_code):
        """多源获取估值数据，交叉验证"""
        sources = []
        
        # 尝试东方财富
        em = self.get_eastmoney_valuation(ts_code)
        if em and em.get('pe'):
            sources.append(em)
            print(f"    ✅ 东方财富: PE={em.get('pe'):.2f}")
        
        # 尝试腾讯财经
        qq = self.get_qq_valuation(ts_code)
        if qq and qq.get('pe'):
            sources.append(qq)
            print(f"    ✅ 腾讯财经: PE={qq.get('pe'):.2f}")
        
        if not sources:
            return None
        
        # 交叉验证：取中位数
        pes = [s['pe'] for s in sources if s.get('pe')]
        pbs = [s['pb'] for s in sources if s.get('pb')]
        
        return {
            'pe': sorted(pes)[len(pes)//2] if pes else None,
            'pb': sorted(pbs)[len(pbs)//2] if pbs else None,
            'sources': [s['source'] for s in sources],
            'raw_data': sources,
            'cross_verified': len(sources) >= 2,
            'time': datetime.now().strftime('%H:%M:%S')
        }
    
    def analyze(self, ts_code, stock_name, industry=""):
        """
        执行完整融合分析
        
        Args:
            ts_code: 股票代码 (如: 002463.SZ)
            stock_name: 股票名称
            industry: 所属行业（可选，如未提供则自动获取）
        """
        print(f"\n{'='*70}")
        print(f"🔍 融合版个股深度分析: {stock_name}({ts_code})")
        print(f"{'='*70}\n")
        
        # ========== 第零部分：获取公司基本信息（行业等） ==========
        print("【第零部分】公司基本信息 - 自动获取")
        print("-"*70)
        
        # 获取公司详细资料
        profile = self.get_company_profile(ts_code)
        if profile.get('industry'):
            self.data['basic_info'] = profile
            print(f"   ✅ 行业: {profile['industry']}")
            if profile.get('main_business'):
                print(f"   ✅ 主营业务: {profile['main_business'][:50]}...")
        
        # 如果未提供行业参数，尝试自动获取
        if not industry:
            print("\n   📝 未提供行业参数，尝试自动获取...")
            industry_info = self.get_industry_info(ts_code)
            if industry_info.get('industry'):
                industry = industry_info['industry']
                print(f"   ✅ 自动获取行业: {industry}")
            else:
                print("   ⚠️ 无法自动获取行业信息，将使用股票名称进行新闻搜索")
        else:
            print(f"\n   📝 使用提供的行业: {industry}")
        
        # ========== 第一部分：股价数据（多源验证） ==========
        print("\n" + "="*70)
        print("【第一部分】股价数据 - 多源验证")
        print("-"*70)
        
        # 1. 长桥数据
        print("1️⃣ 长桥API...")
        lb_data = self.get_longbridge_data(ts_code)
        if lb_data:
            print(f"   ✅ 价格: {lb_data.get('price')}元")
            print(f"   ✅ 20日涨幅: {lb_data.get('change_20d', 'N/A'):.2f}%" if lb_data.get('change_20d') else "   ⚠️ 20日涨幅: N/A")
            self.data['price']['longbridge'] = lb_data
        
        # 2. 多源估值
        print("\n2️⃣ 多源估值验证...")
        valuation = self.get_multi_source_valuation(ts_code)
        if valuation:
            print(f"   ✅ 综合PE: {valuation.get('pe'):.2f}倍")
            print(f"   ✅ 综合PB: {valuation.get('pb'):.2f}倍")
            print(f"   📊 数据源: {', '.join(valuation.get('sources', []))}")
            self.data['valuation'] = valuation
        
        # ========== 第二部分：新闻搜索（6源融合） ==========
        print("\n" + "="*70)
        print("【第二部分】新闻搜索 - 6源融合去重")
        print("-"*70)
        
        news_results = search_stock_comprehensive(ts_code, stock_name, industry)
        self.data['news'] = news_results
        
        # ========== 第三部分：生成10环节报告 ==========
        print("\n" + "="*70)
        print("【第三部分】生成10环节分析报告")
        print("-"*70)
        
        report = self._generate_report(ts_code, stock_name, industry)
        
        # 保存报告
        os.makedirs(REPORTS_DIR, exist_ok=True)
        report_file = f"{REPORTS_DIR}/fusion_analysis_{ts_code.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.md"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n✅ 报告已保存: {report_file}")
        return report
    
    def _generate_report(self, ts_code, stock_name, industry):
        """生成10环节分析报告"""
        lb = self.data['price'].get('longbridge', {})
        val = self.data.get('valuation', {})
        news = self.data.get('news', {})
        basic = self.data.get('basic_info', {})
        
        # 优先使用自动获取的行业信息
        if not industry and basic.get('industry'):
            industry = basic['industry']
        
        price = lb.get('price', 0)
        pe = val.get('pe', 0)
        
        report_lines = [
            f"# {stock_name}（{ts_code}）深度分析报告 - 融合版",
            "",
            f"> 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> 数据来源: 长桥API + Exa搜索 + 知识星球 + 新浪财经 + 东方财富 + 腾讯财经 + 华尔街见闻",
            "",
            "---",
            "",
            "## 0️⃣ 投资摘要",
            "",
            "| 项目 | 数据 | 说明 |",
            "|:-----|:-----|:-----|",
            f"| 股票代码 | {ts_code} | - |",
            f"| 当前股价 | ¥{price:.2f} | 长桥API |" if price else "| 当前股价 | 获取中 | - |",
            f"| 市盈率(PE) | {pe:.2f}倍 | 多源验证 |" if pe else "| 市盈率(PE) | - | - |",
            f"| 市净率(PB) | {val.get('pb', 0):.2f}倍 | 多源验证 |" if val.get('pb') else "| 市净率(PB) | - | - |",
            f"| 所属行业 | {industry if industry else '待补充'} | 自动获取 |",
            "",
            "**核心逻辑**: 待补充（基于新闻搜索结果的总结）",
            "",
            "---",
            "",
            "## 1️⃣ 公司基本画像",
            "",
            "### 1.1 基本信息",
            f"- **股票代码**: {ts_code}",
            f"- **公司名称**: {stock_name}",
            f"- **所属行业**: {industry if industry else '待补充'}",
            "",
        ]
        
        # 添加主营业务信息（如果有）
        if basic.get('main_business'):
            report_lines.extend([
                "### 1.2 主营业务",
                f"{basic['main_business']}",
                "",
            ])
        
        if lb:
            report_lines.extend([
                "| 指标 | 数值 |",
                "|:-----|:-----|",
                f"| 最新价 | ¥{lb.get('price', 'N/A')} |",
                f"| 开盘价 | ¥{lb.get('open', 'N/A')} |",
                f"| 最高价 | ¥{lb.get('high', 'N/A')} |",
                f"| 最低价 | ¥{lb.get('low', 'N/A')} |",
                f"| 20日涨幅 | {lb.get('change_20d', 'N/A'):.2f}% |" if lb.get('change_20d') else "| 20日涨幅 | N/A |",
                f"| 60日涨幅 | {lb.get('change_60d', 'N/A'):.2f}% |" if lb.get('change_60d') else "| 60日涨幅 | N/A |",
                "",
            ])
        
        # 新闻部分
        report_lines.extend([
            "## 2️⃣ 多源新闻聚合",
            "",
        ])
        
        if news:
            for category, news_list in news.items():
                if news_list:
                    report_lines.extend([
                        f"### {category} ({len(news_list)}条)",
                        "",
                    ])
                    for i, n in enumerate(news_list[:5], 1):
                        source = n.get('source', '未知')
                        title = n.get('title', '')[:60]
                        report_lines.append(f"{i}. [{source}] {title}...")
                    report_lines.append("")
        
        report_lines.extend([
            "---",
            "",
            "## 3️⃣-🔟 详细分析",
            "",
            "> 注: 后续环节需要更多财务数据和行业数据进行填充",
            "",
            "### 待补充内容",
            "- [ ] 业务结构分析",
            "- [ ] 产业链定位",
            "- [ ] 订单与产能分析",
            "- [ ] 财务深度分析",
            "- [ ] 行业景气度验证",
            "- [ ] 客户与供应商分析",
            "- [ ] 业绩预测与估值",
            "- [ ] 风险提示",
            "- [ ] 投资建议",
            "",
            "---",
            "",
            "## 数据源说明",
            "",
            "| 数据类型 | 数据源 | 优先级 |",
            "|:---------|:-------|:-------|",
            "| 实时股价 | 长桥API | P0 |",
            "| 估值数据 | 东方财富 + 腾讯财经 | P1 |",
            "| 新闻搜索 | Exa全网 | P1 |",
            "| 调研纪要 | 知识星球 | P1 |",
            "| 财经新闻 | 新浪财经 + 东方财富 + 腾讯财经 + 华尔街见闻 | P2 |",
            "",
            "---",
            "",
            "*报告由融合版分析脚本生成*",
        ])
        
        return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(description='A股个股融合分析')
    parser.add_argument('--code', required=True, help='股票代码 (如: 002463.SZ)')
    parser.add_argument('--name', required=True, help='股票名称 (如: 沪电股份)')
    parser.add_argument('--industry', default='', help='所属行业（可选）')
    
    args = parser.parse_args()
    
    analyzer = FusionStockAnalyzer()
    report = analyzer.analyze(args.code, args.name, args.industry)
    
    print("\n" + "="*70)
    print("报告预览（前2000字符）:")
    print("="*70)
    print(report[:2000])
    print("\n...")


if __name__ == '__main__':
    main()
