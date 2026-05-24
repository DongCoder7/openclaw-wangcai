#!/root/.openclaw/workspace/venv/bin/python3
"""
Multi-Source Search v1.0 - Unified search interface
Integrates: Exa AI Search, Knowledge Base (zsxq), Sina Finance API

Usage:
    python3 multi_source_search.py --keyword "硅光" --days 30
    python3 multi_source_search.py --stock_code 300308.SZ --stock_name 中际旭创 --industry 光模块
    python3 multi_source_search.py --industry 半导体 --upstream "硅片 光刻胶" --downstream "芯片设计 封测"
"""

import sys
import json
import os
import re
import subprocess
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# Add paths for importing
sys.path.insert(0, str(Path(__file__).parent))


class MultiSourceSearcher:
    """Unified multi-source search interface."""
    
    def __init__(self):
        self.raw_dir = Path('/root/.openclaw/workspace/data/zsxq/raw')
        self.results = defaultdict(list)
    
    # ─────────────────────────────────────────
    # P1: Exa AI Search
    # ─────────────────────────────────────────
    def search_exa(self, query: str, num_results: int = 10) -> list:
        """Call Exa web search via mcporter."""
        try:
            cmd = [
                'mcporter', 'call',
                f'exa.web_search_exa({{"query": "{query}", "numResults": {num_results}}})'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                # Parse mcporter output - lines with Title/URL/Highlights
                output = result.stdout
                entries = []
                current = {}
                for line in output.split('\n'):
                    if line.startswith('Title:'):
                        if current:
                            entries.append(current)
                        current = {'title': line[6:].strip(), 'source': 'Exa'}
                    elif line.startswith('URL:'):
                        current['url'] = line[4:].strip()
                    elif line.startswith('Highlights:'):
                        current['highlights'] = []
                    elif line.startswith('[...]'):
                        pass
                    elif 'highlights' in current and line.strip() and not line.startswith('Title:') and not line.startswith('URL:'):
                        if not line.startswith('Published:') and not line.startswith('Author:'):
                            current['highlights'].append(line.strip())
                if current:
                    entries.append(current)
                return entries
            else:
                return [{'error': f'Exa search failed: {result.stderr}', 'source': 'Exa'}]
        except Exception as e:
            return [{'error': f'Exa search exception: {str(e)}', 'source': 'Exa'}]
    
    # ─────────────────────────────────────────
    # P2: Knowledge Base (zsxq) Search
    # ─────────────────────────────────────────
    def search_zsxq(self, keyword: str, days: int = 30, max_results: int = 50) -> list:
        """Search zsxq historical data for keyword."""
        if not self.raw_dir.exists():
            return [{'error': 'zsxq raw data directory not found', 'source': 'zsxq'}]
        
        results = []
        files = sorted(self.raw_dir.glob('*.json'))
        cutoff = datetime.now() - timedelta(days=days)
        
        for f in files:
            # Parse date from filename
            try:
                date_str = f.name[:10]
                file_date = datetime.strptime(date_str, '%Y-%m-%d')
                if file_date < cutoff:
                    continue
            except:
                continue
            
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                topics = data if isinstance(data, list) else [data]
                for topic in topics:
                    content = topic.get('content', '') + ' ' + topic.get('title', '')
                    if keyword in content:
                        results.append({
                            'date': topic.get('date', date_str),
                            'title': topic.get('title', '')[:100],
                            'content': content[:500].strip(),
                            'author': topic.get('author', '')[:30],
                            'source': 'zsxq',
                            'file': f.name
                        })
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
            except Exception as e:
                continue
        
        return results
    
    def search_zsxq_multi(self, keywords: list, days: int = 30, max_results: int = 50) -> dict:
        """Search zsxq with multiple keywords."""
        results = {}
        for kw in keywords:
            results[kw] = self.search_zsxq(kw, days, max_results)
        return results
    
    # ─────────────────────────────────────────
    # P3: Sina Finance API
    # ─────────────────────────────────────────
    def search_sina(self, category: str = 'finance', num: int = 20) -> list:
        """Fetch news from Sina Finance API."""
        # Category mapping: finance=2516, tech=2517, stock=2512
        lid_map = {'finance': '2516', 'tech': '2517', 'stock': '2512'}
        lid = lid_map.get(category, '2516')
        
        try:
            cmd = [
                'curl', '-s',
                f'https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid={lid}&num={num}&k=&_='
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                data = json.loads(result.stdout)
                items = data.get('result', {}).get('data', [])
                return [{
                    'title': item.get('title', ''),
                    'url': item.get('url', ''),
                    'time': item.get('time', ''),
                    'source': 'Sina'
                } for item in items]
            else:
                return [{'error': f'Sina API failed: {result.stderr}', 'source': 'Sina'}]
        except Exception as e:
            return [{'error': f'Sina API exception: {str(e)}', 'source': 'Sina'}]
    
    # ─────────────────────────────────────────
    # Combined Search
    # ─────────────────────────────────────────
    def search_all(self, keyword: str, days: int = 30, num_exa: int = 10) -> dict:
        """Execute P1+P2+P3 search for a keyword."""
        return {
            'P1_Exa': self.search_exa(keyword, num_exa),
            'P2_zsxq': self.search_zsxq(keyword, days),
            'P3_Sina': self.search_sina('finance', 20),
            'keyword': keyword,
            'search_time': datetime.now().isoformat()
        }


# ─────────────────────────────────────────
# High-Level Interfaces
# ─────────────────────────────────────────

def search_stock_comprehensive(stock_code: str, stock_name: str, industry: str = '') -> dict:
    """
    Comprehensive 6-category search for a stock.
    Categories: basics, capital_ops, risk, business_drivers, earnings, capital_market
    """
    searcher = MultiSourceSearcher()
    results = {}
    
    # Category 1: Basics - industry/business
    query = f"{stock_name} {industry} 业务 产品"
    results['基础'] = searcher.search_exa(query, 5)
    
    # Category 2: Capital operations
    query = f"{stock_name} 并购 收购 定增 重组"
    results['资本运作'] = searcher.search_exa(query, 5)
    
    # Category 3: Risk
    query = f"{stock_name} 减持 增持 违规 处罚 监管 问询函"
    results['风险'] = searcher.search_exa(query, 5)
    
    # Category 4: Business drivers
    query = f"{stock_name} 订单 合同 中标 产能扩张 技术突破"
    results['业务驱动'] = searcher.search_exa(query, 5)
    
    # Category 5: Earnings
    query = f"{stock_name} 业绩预增 业绩快报 业绩下修 扭亏"
    results['业绩'] = searcher.search_exa(query, 5)
    
    # Category 6: Capital market
    query = f"{stock_name} 研报 评级 目标价 机构调研"
    results['资本市场'] = searcher.search_exa(query, 5)
    
    # P2: zsxq search
    results['知识星球'] = searcher.search_zsxq(stock_name, days=30, max_results=30)
    
    return results


def search_industry_chain_news(industry: str, upstream: str = '', downstream: str = '', days: int = 30) -> dict:
    """
    Search industry chain news across sources.
    """
    searcher = MultiSourceSearcher()
    results = {}
    
    # Industry level
    results['行业'] = searcher.search_all(industry, days)
    
    # Upstream
    if upstream:
        results['上游'] = searcher.search_all(f"{industry} {upstream}", days)
    
    # Downstream
    if downstream:
        results['下游'] = searcher.search_all(f"{industry} {downstream}", days)
    
    return results


def search_multi_source_news(keyword: str, stock_code: str = '', stock_name: str = '', days: int = 30) -> dict:
    """
    General multi-source news search.
    """
    searcher = MultiSourceSearcher()
    return searcher.search_all(keyword, days)


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Multi-Source Search')
    parser.add_argument('--keyword', type=str, help='Search keyword')
    parser.add_argument('--stock_code', type=str, help='Stock code')
    parser.add_argument('--stock_name', type=str, help='Stock name')
    parser.add_argument('--industry', type=str, help='Industry name')
    parser.add_argument('--upstream', type=str, help='Upstream keywords')
    parser.add_argument('--downstream', type=str, help='Downstream keywords')
    parser.add_argument('--days', type=int, default=30, help='Days to search back')
    parser.add_argument('--output', type=str, help='Output JSON file')
    
    args = parser.parse_args()
    
    if args.stock_code and args.stock_name:
        result = search_stock_comprehensive(args.stock_code, args.stock_name, args.industry or '')
    elif args.industry:
        result = search_industry_chain_news(args.industry, args.upstream or '', args.downstream or '', args.days)
    elif args.keyword:
        result = search_multi_source_news(args.keyword, args.stock_code or '', args.stock_name or '', args.days)
    else:
        print("Usage: python3 multi_source_search.py --keyword '硅光' --days 30")
        print("       python3 multi_source_search.py --stock_code 300308.SZ --stock_name 中际旭创")
        print("       python3 multi_source_search.py --industry 半导体 --upstream '硅片 光刻胶' --downstream '芯片设计'")
        sys.exit(1)
    
    # Output
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"Results saved to {args.output}")
    else:
        print(output_json[:5000])  # Print first 5000 chars
        if len(output_json) > 5000:
            print(f"\n... (truncated, total {len(output_json)} chars)")
