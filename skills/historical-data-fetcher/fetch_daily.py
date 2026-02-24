#!/usr/bin/env python3
"""
批量获取日线数据
支持多数据源自动回退
"""
import sys
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

# Add parent to path
sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')

from sources.local_source import LocalSource
from sources.tencent_source import TencentSource
from sources.akshare_source import AKShareSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


def get_stock_list_from_local() -> list:
    """从本地数据库获取股票列表"""
    source = LocalSource(DB_PATH)
    df = source.get_stock_list()
    if df is not None:
        return df['ts_code'].tolist()
    return []


def fetch_daily_data(codes: list, start: str, end: str, source_name: str = 'auto'):
    """
    批量获取日线数据
    
    Args:
        codes: 股票代码列表
        start: 开始日期 (YYYYMMDD)
        end: 结束日期 (YYYYMMDD)
        source_name: 数据源名称 ('akshare', 'tencent', 'local', 'auto')
    
    Returns:
        Dict with results and statistics
    """
    results = {
        'start_time': datetime.now().isoformat(),
        'codes_requested': len(codes),
        'codes_success': 0,
        'codes_failed': 0,
        'data': {}
    }
    
    # Initialize sources
    sources = {}
    
    if source_name in ['auto', 'akshare']:
        akshare = AKShareSource()
        if akshare.available:
            sources['akshare'] = akshare
            print(f"✅ AKShare available")
    
    if source_name in ['auto', 'tencent']:
        tencent = TencentSource()
        if tencent.available:
            sources['tencent'] = tencent
            print(f"✅ Tencent API available")
    
    if source_name in ['auto', 'local']:
        local = LocalSource(DB_PATH)
        if local.available:
            sources['local'] = local
            print(f"✅ Local DB available")
    
    if not sources:
        print("❌ No data sources available!")
        return results
    
    # Fetch data
    print(f"\nFetching data for {len(codes)} stocks...")
    print(f"Date range: {start} - {end}")
    print("-" * 60)
    
    for i, code in enumerate(codes):
        if (i + 1) % 100 == 0:
            print(f"Progress: {i+1}/{len(codes)} ({(i+1)/len(codes)*100:.1f}%)")
        
        fetched = False
        
        # Try sources in priority order
        for src_name in ['akshare', 'tencent', 'local']:
            if src_name not in sources:
                continue
            
            source = sources[src_name]
            
            try:
                df = source.get_daily_data(code, start, end)
                if df is not None and not df.empty:
                    results['data'][code] = df.to_dict('records')
                    results['codes_success'] += 1
                    fetched = True
                    break
            except Exception as e:
                continue
        
        if not fetched:
            results['codes_failed'] += 1
    
    results['end_time'] = datetime.now().isoformat()
    
    # Summary
    print("-" * 60)
    print(f"✅ Success: {results['codes_success']}")
    print(f"❌ Failed: {results['codes_failed']}")
    print(f"Success rate: {results['codes_success']/len(codes)*100:.1f}%")
    
    return results


def update_latest_only():
    """只更新最新日期的数据"""
    print("Updating latest data only...")
    
    # Get latest date from local DB
    local = LocalSource(DB_PATH)
    latest = local.get_latest_date()
    
    if latest:
        print(f"Latest data in DB: {latest}")
        today = datetime.now().strftime('%Y%m%d')
        
        if latest >= today:
            print("✅ Data is already up to date")
            return
        
        # Get stock list
        codes = get_stock_list_from_local()
        
        if codes:
            # Fetch from next day to today
            start = (datetime.strptime(latest, '%Y%m%d') + timedelta(days=1)).strftime('%Y%m%d')
            fetch_daily_data(codes[:100], start, today)  # Limit to 100 for testing


def main():
    parser = argparse.ArgumentParser(description='Fetch daily stock data')
    parser.add_argument('--codes', type=str, help='Comma-separated stock codes (e.g., 000001.SZ,600519.SH)')
    parser.add_argument('--source', type=str, default='auto', choices=['auto', 'akshare', 'tencent', 'local'])
    parser.add_argument('--start', type=str, help='Start date (YYYYMMDD)')
    parser.add_argument('--end', type=str, help='End date (YYYYMMDD)')
    parser.add_argument('--update', action='store_true', help='Update only latest data')
    parser.add_argument('--all', action='store_true', help='Fetch all stocks')
    parser.add_argument('--limit', type=int, default=100, help='Limit number of stocks (for testing)')
    parser.add_argument('--output', type=str, help='Output JSON file')
    
    args = parser.parse_args()
    
    if args.update:
        update_latest_only()
        return
    
    # Determine codes to fetch
    if args.all:
        codes = get_stock_list_from_local()
        print(f"Found {len(codes)} stocks in local DB")
        codes = codes[:args.limit]
    elif args.codes:
        codes = args.codes.split(',')
    else:
        # Default test codes
        codes = ['000001.SZ', '600519.SH', '000858.SZ', '600036.SH', '601318.SH']
    
    # Determine date range
    if args.start and args.end:
        start, end = args.start, args.end
    else:
        # Default: last 30 days
        end = datetime.now().strftime('%Y%m%d')
        start = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
    
    # Fetch data
    results = fetch_daily_data(codes, start, end, args.source)
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nResults saved to: {args.output}")
    
    # Also save to default location
    output_dir = Path('/root/.openclaw/workspace/data')
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_output = output_dir / f'fetched_data_{timestamp}.json'
    
    with open(default_output, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Results saved to: {default_output}")


if __name__ == '__main__':
    main()
