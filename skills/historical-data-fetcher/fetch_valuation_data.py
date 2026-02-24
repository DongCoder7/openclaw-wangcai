#!/usr/bin/env python3
"""
获取全市场实时估值数据（腾讯API）
用于补充PE/PB等估值因子
"""
import sys
import sqlite3
import pandas as pd
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')
from sources.local_source import LocalSource
from sources.tencent_source import TencentSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


def fetch_all_stocks_valuation():
    """获取全市场估值数据"""
    print("="*60)
    print("获取全市场估值数据 (腾讯API)")
    print("="*60)
    
    # Get stock list from local DB
    local = LocalSource(DB_PATH)
    stocks = local.get_stock_list()
    
    if stocks is None or stocks.empty:
        print("❌ 无法获取股票列表")
        return None
    
    codes = stocks['ts_code'].tolist()
    print(f"本地数据库股票数: {len(codes)}")
    
    # Fetch from Tencent API
    tencent = TencentSource()
    if not tencent.available:
        print("❌ 腾讯API不可用")
        return None
    
    print(f"\n开始获取实时估值数据...")
    
    all_data = []
    batch_size = 100
    total_batches = (len(codes) + batch_size - 1) // batch_size
    
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        try:
            df = tencent.get_realtime_quotes(batch)
            if df is not None and not df.empty:
                all_data.append(df)
            
            if batch_num % 10 == 0 or batch_num == total_batches:
                print(f"  进度: {batch_num}/{total_batches} ({min(i+batch_size, len(codes))}/{len(codes)})")
                
        except Exception as e:
            print(f"  批次 {batch_num} 失败: {e}")
            continue
    
    if not all_data:
        print("❌ 未获取到数据")
        return None
    
    # Combine all data
    combined = pd.concat(all_data, ignore_index=True)
    print(f"\n✅ 成功获取 {len(combined)} 只股票数据")
    
    # Show statistics
    print(f"\n估值数据概况:")
    print(f"  有PE数据: {combined['pe'].notna().sum()} 只")
    print(f"  有PB数据: {combined['pb'].notna().sum()} 只")
    print(f"  有市值数据: {combined['market_cap'].notna().sum()} 只")
    
    # Save to database
    save_valuation_to_db(combined)
    
    return combined


def save_valuation_to_db(df: pd.DataFrame):
    """保存估值数据到数据库"""
    trade_date = datetime.now().strftime('%Y%m%d')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_valuation (
            ts_code TEXT,
            trade_date TEXT,
            price REAL,
            pe REAL,
            pb REAL,
            market_cap REAL,
            turnover_rate REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """)
    
    # Insert data
    inserted = 0
    for _, row in df.iterrows():
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO stock_valuation 
                (ts_code, trade_date, price, pe, pb, market_cap, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row['ts_code'],
                trade_date,
                row.get('price'),
                row.get('pe'),
                row.get('pb'),
                row.get('market_cap'),
                row.get('turnover_rate')
            ))
            inserted += 1
        except Exception as e:
            continue
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 已保存 {inserted} 条记录到 stock_valuation 表")


def merge_factors_with_valuation():
    """合并技术因子和估值数据"""
    print("\n" + "="*60)
    print("合并技术因子和估值数据")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Check if valuation table exists
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stock_valuation'")
    if not cursor.fetchone():
        print("❌ stock_valuation 表不存在，请先运行获取估值数据")
        conn.close()
        return
    
    # Get latest date
    cursor.execute("SELECT MAX(trade_date) FROM stock_valuation")
    latest_val_date = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
    latest_factor_date = cursor.fetchone()[0]
    
    print(f"估值数据最新日期: {latest_val_date}")
    print(f"因子数据最新日期: {latest_factor_date}")
    
    # Merge data for analysis
    query = f"""
    SELECT 
        f.ts_code,
        f.trade_date,
        f.ret_20,
        f.ret_60,
        f.ret_120,
        f.vol_20,
        f.vol_ratio,
        f.price_pos_20,
        f.price_pos_60,
        f.money_flow,
        f.rel_strength,
        v.pe,
        v.pb,
        v.market_cap,
        v.turnover_rate
    FROM stock_factors f
    LEFT JOIN stock_valuation v ON f.ts_code = v.ts_code AND f.trade_date = v.trade_date
    WHERE f.trade_date = '{latest_factor_date}'
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"\n合并后数据: {len(df)} 只股票")
    print(f"  有PE数据: {df['pe'].notna().sum()}")
    print(f"  有PB数据: {df['pb'].notna().sum()}")
    
    # Save merged data
    output_file = f'/root/.openclaw/workspace/data/merged_factors_{latest_factor_date}.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ 合并数据已保存: {output_file}")
    
    return df


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--fetch', action='store_true', help='获取估值数据')
    parser.add_argument('--merge', action='store_true', help='合并数据')
    parser.add_argument('--all', action='store_true', help='执行全部')
    
    args = parser.parse_args()
    
    if args.fetch or args.all:
        fetch_all_stocks_valuation()
    
    if args.merge or args.all:
        merge_factors_with_valuation()
    
    if not any([args.fetch, args.merge, args.all]):
        print("使用方法:")
        print("  python3 fetch_valuation_data.py --fetch   # 获取估值数据")
        print("  python3 fetch_valuation_data.py --merge   # 合并数据")
        print("  python3 fetch_valuation_data.py --all     # 执行全部")
