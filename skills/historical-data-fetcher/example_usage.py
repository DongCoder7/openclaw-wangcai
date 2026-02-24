#!/usr/bin/env python3
"""
SKILL使用示例 - 历史数据获取器
展示如何使用historical-data-fetcher skill
"""
import sys
sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')

from sources.local_source import LocalSource
from sources.tencent_source import TencentSource
from fetch_factors import FactorDataFetcher

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


def example_1_test_sources():
    """示例1: 测试数据源可用性"""
    print("="*60)
    print("示例1: 测试数据源可用性")
    print("="*60)
    
    # Test local database
    local = LocalSource(DB_PATH)
    print(f"本地数据库: {'✅ 可用' if local.available else '❌ 不可用'}")
    
    # Test Tencent API
    tencent = TencentSource()
    print(f"腾讯API: {'✅ 可用' if tencent.available else '❌ 不可用'}")


def example_2_get_stock_list():
    """示例2: 获取股票列表"""
    print("\n" + "="*60)
    print("示例2: 获取股票列表")
    print("="*60)
    
    local = LocalSource(DB_PATH)
    stocks = local.get_stock_list()
    
    if stocks is not None:
        print(f"本地数据库共有 {len(stocks)} 只股票")
        print(f"\n前5只:")
        for i, code in enumerate(stocks['ts_code'].head(5), 1):
            print(f"  {i}. {code}")


def example_3_get_daily_data():
    """示例3: 获取日线数据"""
    print("\n" + "="*60)
    print("示例3: 获取日线数据")
    print("="*60)
    
    local = LocalSource(DB_PATH)
    
    # Get data for specific stock
    code = '002390.SZ'
    df = local.get_daily_data(code, '20260201', '20260224')
    
    if df is not None:
        print(f"获取到 {code} 的 {len(df)} 天数据")
        print(f"\n数据列: {list(df.columns)}")
        print(f"\n最近5天:")
        print(df.tail())


def example_4_get_realtime_quotes():
    """示例4: 获取实时行情"""
    print("\n" + "="*60)
    print("示例4: 获取实时行情 (腾讯API)")
    print("="*60)
    
    tencent = TencentSource()
    
    if not tencent.available:
        print("腾讯API不可用")
        return
    
    # Get realtime quotes
    codes = ['000001.SZ', '600519.SH', '000858.SZ']
    df = tencent.get_realtime_quotes(codes)
    
    if df is not None:
        print(f"获取到 {len(df)} 只股票实时行情")
        print(f"\n{df[['ts_code', 'name', 'price', 'change_pct', 'pe', 'pb']].to_string()}")


def example_5_get_factor_summary():
    """示例5: 获取因子数据概况"""
    print("\n" + "="*60)
    print("示例5: 因子数据概况")
    print("="*60)
    
    fetcher = FactorDataFetcher(DB_PATH)
    summary = fetcher.get_latest_data_summary()
    
    print(f"最新数据日期: {summary['latest_date']}")
    print(f"股票数量: {summary['stock_count']}")
    print(f"可用因子数: {summary['factor_count']}")
    print(f"\n因子列表:")
    for factor in summary['available_factors']:
        print(f"  - {factor}")
    
    fetcher.close()


def example_6_data_coverage():
    """示例6: 数据覆盖情况"""
    print("\n" + "="*60)
    print("示例6: 数据覆盖情况")
    print("="*60)
    
    local = LocalSource(DB_PATH)
    coverage = local.get_date_coverage()
    
    if coverage:
        print(f"总股票数: {coverage['total_stocks']}")
        print(f"时间范围: {coverage['start_date']} ~ {coverage['end_date']}")
        print(f"总记录数: {coverage['total_records']:,}")
        
        if coverage.get('recent_coverage'):
            print(f"\n最近10天数据覆盖:")
            for date, count in coverage['recent_coverage']:
                print(f"  {date}: {count} 只股票")


def main():
    print("="*60)
    print("Historical Data Fetcher Skill - 使用示例")
    print("="*60)
    
    # Run all examples
    example_1_test_sources()
    example_2_get_stock_list()
    example_3_get_daily_data()
    example_4_get_realtime_quotes()
    example_5_get_factor_summary()
    example_6_data_coverage()
    
    print("\n" + "="*60)
    print("示例运行完成")
    print("="*60)


if __name__ == '__main__':
    main()
