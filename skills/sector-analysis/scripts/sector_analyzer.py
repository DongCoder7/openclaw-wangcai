#!/usr/bin/env python3
"""
板块投资分析系统 - Sector Analysis System v1.0
基于方法论：零硬编码，全自动发现标的
"""

import requests
import json
import re
import sys
import os
from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from collections import Counter

# 添加路径
sys.path.insert(0, '/root/.openclaw/workspace/skills/dounai-investment-system/scripts')

try:
    from multi_source_news_v2 import MultiSourceNewsSearcher, ZsxqSearcher
    MULTI_SOURCE_AVAILABLE = True
except ImportError:
    MULTI_SOURCE_AVAILABLE = False
    print("⚠️ multi_source_news_v2 未找到")


class SectorAnalyzer:
    """板块分析器 - 全自动发现标的，零硬编码"""
    
    def __init__(self):
        self.news_searcher = MultiSourceNewsSearcher() if MULTI_SOURCE_AVAILABLE else None
        self.zsxq_searcher = ZsxqSearcher() if MULTI_SOURCE_AVAILABLE else None
        
    def scan_sector_stocks(self, sector_name: str, keywords: List[str]) -> List[Dict]:
        """
        Step 1: 扫描板块内所有标的（自动发现，不硬编码）
        
        Args:
            sector_name: 板块名称
            keywords: 板块关键词列表
            
        Returns:
            板块内标的列表，按提及次数排序
        """
        print(f"\n{'='*80}")
        print(f"🔍 Step 1: 扫描板块 [{sector_name}] 标的")
        print(f"{'='*80}")
        
        all_mentions = []
        
        # P1: Exa全网搜索 - 发现板块内公司
        if self.news_searcher:
            print("\n📡 Exa全网搜索发现标的...")
            for kw in keywords[:3]:  # 前3个关键词
                try:
                    # 搜索板块概念股
                    query = f"{kw} 概念股 龙头 上市公司 A股"
                    news = self.news_searcher._search_exa(query, num=15)
                    for n in news:
                        text = n.get('title', '') + ' ' + n.get('content', '')
                        stocks = self._extract_stocks_from_text(text)
                        for s in stocks:
                            all_mentions.append({
                                **s,
                                'source': 'Exa',
                                'keyword': kw
                            })
                    print(f"  ✓ 关键词'{kw}': 发现 {len(news)} 条新闻")
                except Exception as e:
                    print(f"  ✗ 搜索失败: {e}")
        
        # P2: 知识星球搜索 - 发现热门标的
        if self.zsxq_searcher:
            print("\n📚 知识星球搜索发现标的...")
            for kw in keywords[:2]:  # 前2个关键词
                try:
                    topics = self.zsxq_searcher.search(kw, count=20)
                    for t in topics:
                        text = t.get('title', '') + ' ' + t.get('content', '')
                        stocks = self._extract_stocks_from_text(text)
                        for s in stocks:
                            all_mentions.append({
                                **s,
                                'source': 'ZSXQ',
                                'keyword': kw
                            })
                    print(f"  ✓ 关键词'{kw}': 发现 {len(topics)} 条话题")
                except Exception as e:
                    print(f"  ✗ 搜索失败: {e}")
        
        # 统计提及次数
        stock_counter = Counter()
        stock_details = {}
        
        for m in all_mentions:
            key = (m['code'], m['name'])
            stock_counter[key] += 1
            if key not in stock_details:
                stock_details[key] = {
                    'code': m['code'],
                    'name': m['name'],
                    'sources': set(),
                    'keywords': set()
                }
            stock_details[key]['sources'].add(m.get('source', 'unknown'))
            stock_details[key]['keywords'].add(m.get('keyword', ''))
        
        # 转换为列表并排序
        unique_stocks = []
        for (code, name), count in stock_counter.most_common(30):
            unique_stocks.append({
                'code': code,
                'name': name,
                'mention_count': count,
                'sources': list(stock_details[(code, name)]['sources']),
                'keywords': list(stock_details[(code, name)]['keywords'])
            })
        
        print(f"\n✅ 共发现 {len(unique_stocks)} 只标的（去重后）")
        print(f"📊 提及次数TOP5:")
        for i, s in enumerate(unique_stocks[:5], 1):
            print(f"   {i}. {s['name']}({s['code']}): {s['mention_count']}次")
        
        return unique_stocks
    
    def _extract_stocks_from_text(self, text: str) -> List[Dict]:
        """从文本中提取股票代码和名称"""
        stocks = []
        
        # 匹配模式: 名称(代码) 或 代码 名称
        # 6位数字代码
        import re
        
        # 匹配 (300308.SZ) 或 (300308)
        pattern1 = r'([\u4e00-\u9fa5]{2,8})\s*[\(（](\d{6})\.[A-Z]{2}[\)）]'
        matches1 = re.findall(pattern1, text)
        for name, code in matches1:
            suffix = 'SZ' if code.startswith(('0', '3')) else 'SH'
            stocks.append({'name': name, 'code': f"{code}.{suffix}"})
        
        # 匹配 代码.后缀 格式
        pattern2 = r'(\d{6})\.(SZ|SH|sz|sh)'
        matches2 = re.findall(pattern2, text)
        for code, suffix in matches2:
            stocks.append({'name': f'股票{code}', 'code': f"{code}.{suffix.upper()}"})
        
        return stocks
    
    def get_realtime_data(self, stocks: List[Dict]) -> List[Dict]:
        """
        获取标的实时行情数据
        """
        print(f"\n{'='*80}")
        print("📈 Step 2: 获取实时行情数据")
        print(f"{'='*80}")
        
        enriched_stocks = []
        
        for i, stock in enumerate(stocks):
            try:
                code = stock['code']
                pure_code = code.split('.')[0]
                prefix = 'sz' if code.startswith('3') or code.startswith('0') else 'sh'
                
                # 腾讯财经API
                url = f'https://qt.gtimg.cn/q={prefix}{pure_code}'
                resp = requests.get(url, timeout=5)
                data = resp.text
                
                if '~' in data:
                    parts = data.split('~')
                    if len(parts) > 45:
                        stock['current_price'] = float(parts[3])
                        stock['change_pct'] = float(parts[32])
                        stock['market_cap'] = float(parts[44]) if parts[44] else 0
                        stock['volume'] = float(parts[36]) if len(parts) > 36 else 0
                        stock['turnover'] = float(parts[37]) if len(parts) > 37 else 0
                        enriched_stocks.append(stock)
                        
                if (i + 1) % 10 == 0:
                    print(f"  ✓ 已获取 {i+1}/{len(stocks)} 只标的")
                    
            except Exception as e:
                print(f"  ✗ 获取 {stock['name']} 失败: {e}")
                continue
        
        print(f"\n✅ 成功获取 {len(enriched_stocks)} 只标的行情")
        return enriched_stocks
    
    def score_stock(self, stock: Dict, sector_keywords: List[str]) -> Dict:
        """
        Step 3: 5维动态评分
        """
        score = {
            'total': 0,
            'momentum': 0,      # 动量得分
            'fundamental': 50,  # 基本面得分（默认50，无数据时）
            'catalyst': 0,      # 催化剂得分
            'risk': 50,         # 风险得分（默认50）
            'liquidity': 0      # 流动性得分
        }
        
        # 1. 动量评分（基于涨跌幅）
        change = stock.get('change_pct', 0)
        if change > 10:
            score['momentum'] = 100
        elif change > 5:
            score['momentum'] = 80
        elif change > 0:
            score['momentum'] = 60
        elif change > -3:
            score['momentum'] = 40
        else:
            score['momentum'] = 20
        
        # 2. 催化剂评分（基于提及次数和来源）
        mention = stock.get('mention_count', 0)
        sources = len(stock.get('sources', []))
        score['catalyst'] = min(mention * 10 + sources * 15, 100)
        
        # 3. 流动性评分（基于市值和成交额）
        market_cap = stock.get('market_cap', 0)
        turnover = stock.get('turnover', 0)
        if market_cap > 500:  # 大于500亿
            score['liquidity'] = 90
        elif market_cap > 100:
            score['liquidity'] = 80
        elif market_cap > 50:
            score['liquidity'] = 70
        else:
            score['liquidity'] = 50
        
        # 4. 风险评分（波动率假设）
        if abs(change) > 10:
            score['risk'] = 30  # 高风险
        elif abs(change) > 5:
            score['risk'] = 50
        else:
            score['risk'] = 70
        
        # 加权总分
        weights = {
            'momentum': 0.25,
            'fundamental': 0.15,
            'catalyst': 0.35,
            'risk': 0.15,
            'liquidity': 0.10
        }
        
        score['total'] = sum(score[k] * weights[k] for k in weights)
        
        return score
    
    def analyze_catalysts(self, stock: Dict, sector_keywords: List[str]) -> Dict:
        """
        Step 4: 深度分析催化剂
        """
        print(f"\n  🔍 分析 {stock['name']} 催化剂...")
        
        catalysts = {
            'policy': [],
            'order': [],
            'technology': [],
            'earnings': [],
            'merger': [],
            'score': 0
        }
        
        if not self.news_searcher:
            return catalysts
        
        searches = [
            (f"{stock['name']} 政策 补贴 扶持", 'policy'),
            (f"{stock['name']} 订单 合同 中标", 'order'),
            (f"{stock['name']} 技术突破 专利", 'technology'),
            (f"{stock['name']} 业绩预告 预增", 'earnings'),
            (f"{stock['name']} 并购 收购 重组", 'merger')
        ]
        
        for query, cat_type in searches:
            try:
                news = self.news_searcher._search_exa(query, num=5)
                catalysts[cat_type].extend(news[:3])
            except:
                pass
        
        # 计算催化剂得分
        total_news = sum(len(v) for v in catalysts.values() if isinstance(v, list))
        catalysts['score'] = min(total_news * 15, 100)
        
        return catalysts
    
    def calculate_trade_points(self, stock: Dict) -> Dict:
        """计算买卖点"""
        price = stock.get('current_price', 0)
        change = stock.get('change_pct', 0)
        
        if price == 0:
            return {}
        
        # 基于 catalyst score 计算目标涨幅
        catalyst_score = stock.get('catalyst_score', 50)
        upside = 0.08 + (catalyst_score / 100) * 0.10  # 8-18%涨幅
        
        target = price * (1 + upside)
        stop_loss = price * 0.92  # 8%止损
        
        return {
            'current': price,
            'target': round(target, 2),
            'stop_loss': round(stop_loss, 2),
            'upside_pct': round(upside * 100, 1),
            'buy_range': (round(price * 0.98, 2), round(price * 1.02, 2))
        }
    
    def generate_sector_report(self, sector_name: str, keywords: List[str]) -> str:
        """
        生成完整的板块投资分析报告
        """
        print(f"\n{'='*80}")
        print(f"🎯 开始分析板块: {sector_name}")
        print(f"{'='*80}")
        
        # Step 1: 扫描板块标的
        stocks = self.scan_sector_stocks(sector_name, keywords)
        if not stocks:
            return f"未找到 [{sector_name}] 相关标的"
        
        # Step 2: 获取行情
        stocks = self.get_realtime_data(stocks)
        
        # Step 3: 评分排序
        print(f"\n{'='*80}")
        print("📊 Step 3: 5维评分排序")
        print(f"{'='*80}")
        
        for stock in stocks:
            stock['score'] = self.score_stock(stock, keywords)
        
        # 按总分排序
        stocks.sort(key=lambda x: x['score']['total'], reverse=True)
        
        # Step 4: 深度分析TOP10
        print(f"\n{'='*80}")
        print("🔥 Step 4: 深度分析TOP10标的")
        print(f"{'='*80}")
        
        top_stocks = stocks[:10]
        for stock in top_stocks:
            stock['catalysts'] = self.analyze_catalysts(stock, keywords)
            stock['score']['catalyst'] = stock['catalysts']['score']
            stock['catalyst_score'] = stock['catalysts']['score']
            stock['trade_points'] = self.calculate_trade_points(stock)
        
        # Step 5: 生成报告
        return self._format_report(sector_name, keywords, top_stocks)
    
    def _format_report(self, sector_name: str, keywords: List[str], stocks: List[Dict]) -> str:
        """格式化输出报告"""
        
        lines = [
            f"# 【{sector_name}】投资分析报告",
            f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> 分析标的: 动态发现 {len(stocks)} 只重点标的",
            f"> 搜索关键词: {', '.join(keywords[:3])}",
            "",
            "---",
            "",
            "## 📊 板块热度",
            "",
            "| 指标 | 数值 |",
            "|:-----|:-----|",
        ]
        
        avg_change = sum(s.get('change_pct', 0) for s in stocks) / len(stocks) if stocks else 0
        total_cap = sum(s.get('market_cap', 0) for s in stocks)
        
        lines.extend([
            f"| 分析标的数 | {len(stocks)} 只 |",
            f"| 平均涨跌幅 | {avg_change:+.2f}% |",
            f"| 板块总市值 | {total_cap:.0f} 亿元 |",
            "",
            "---",
            "",
            "## 🏆 投资排序（按综合评分）",
            "",
        ])
        
        for i, stock in enumerate(stocks[:5], 1):
            score = stock.get('score', {})
            trade = stock.get('trade_points', {})
            
            lines.extend([
                f"### 第{i}名: {stock['name']} ({stock['code']})",
                "",
                "| 指标 | 数值 |",
                "|:-----|:-----|",
                f"| 当前价 | {stock.get('current_price', 0):.2f} 元 |",
                f"| 今日涨跌 | {stock.get('change_pct', 0):+.2f}% |",
                f"| 综合评分 | {score.get('total', 0):.1f}/100 |",
                f"| 动量得分 | {score.get('momentum', 0):.0f} |",
                f"| 催化剂得分 | {score.get('catalyst', 0):.0f} |",
                f"| 目标价 | {trade.get('target', 0):.2f} 元 |",
                f"| 预期涨幅 | +{trade.get('upside_pct', 0):.1f}% |",
                f"| 止损价 | {trade.get('stop_loss', 0):.2f} 元 |",
                f"| 买入区间 | {trade.get('buy_range', (0,0))[0]:.2f}-{trade.get('buy_range', (0,0))[1]:.2f} |",
                f"| 提及次数 | {stock.get('mention_count', 0)} 次 |",
                f"| 信息来源 | {', '.join(stock.get('sources', []))} |",
                "",
            ])
        
        lines.extend([
            "---",
            "",
            "## 💰 投资组合建议",
            "",
            "| 标的 | 仓位 | 核心逻辑 |",
            "|:-----|:---:|:---------|",
        ])
        
        positions = ["30%", "25%", "20%", "15%", "10%"]
        for i, stock in enumerate(stocks[:5]):
            pos = positions[i] if i < len(positions) else "10%"
            catalyst = "政策+订单驱动" if stock.get('catalyst_score', 0) > 50 else "技术突破"
            lines.append(f"| {stock['name']} | {pos} | {catalyst} |")
        
        lines.extend([
            "",
            "---",
            "",
            "## ⚠️ 风险提示",
            "",
            "1. 短期涨幅过大存在回调风险",
            "2. 催化剂不及预期导致股价调整",
            "3. 大盘系统性风险",
            "",
            f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
            "*数据来源: Exa全网 + 知识星球 + 腾讯财经*",
        ])
        
        return "\n".join(lines)


# 便捷函数
def analyze_sector(sector_name: str, keywords: List[str]) -> str:
    """分析单个板块"""
    analyzer = SectorAnalyzer()
    return analyzer.generate_sector_report(sector_name, keywords)


def analyze_multiple_sectors(sectors: Dict[str, List[str]]) -> Dict[str, str]:
    """
    分析多个板块
    
    Args:
        sectors: {板块名称: [关键词列表]}
        
    Returns:
        {板块名称: 报告内容}
    """
    analyzer = SectorAnalyzer()
    results = {}
    
    for sector_name, keywords in sectors.items():
        print(f"\n{'='*80}")
        print(f"🚀 开始分析: {sector_name}")
        print(f"{'='*80}")
        
        try:
            report = analyzer.generate_sector_report(sector_name, keywords)
            results[sector_name] = report
            
            # 保存报告
            filename = f"sector_report_{sector_name.replace('/', '_')}_{datetime.now().strftime('%Y%m%d')}.md"
            filepath = f"/root/.openclaw/workspace/reports/{filename}"
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n✅ 报告已保存: {filepath}")
            
        except Exception as e:
            print(f"\n❌ 分析失败: {e}")
            results[sector_name] = f"分析失败: {e}"
    
    return results


if __name__ == "__main__":
    # 测试分析
    print("🧪 测试板块分析系统")
    print("="*80)
    
    # 测试单个板块
    report = analyze_sector("AI电源", ["AI电源", "数据中心电源", "服务器电源"])
    print(report[:2000])
