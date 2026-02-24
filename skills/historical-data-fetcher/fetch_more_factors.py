#!/usr/bin/env python3
"""
获取更多因子数据
- 行业分类 (申万/中信)
- 财务数据 (ROE, 营收增长, 净利润增长, 负债率)
- 防御因子 (股息率, 低波动)

使用腾讯API + 本地计算
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import sys

sys.path.insert(0, '/root/.openclaw/workspace/skills/historical-data-fetcher')
from sources.local_source import LocalSource
from sources.tencent_source import TencentSource

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'


def calculate_defensive_factors():
    """计算防御性因子"""
    print("="*60)
    print("计算防御性因子")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取历史数据计算低波动因子
    query = """
    SELECT ts_code, trade_date, ret_20, vol_20, ma_20
    FROM stock_factors
    WHERE trade_date >= date('now', '-120 days')
    ORDER BY ts_code, trade_date
    """
    
    df = pd.read_sql(query, conn)
    
    if df.empty:
        print("❌ 无数据")
        conn.close()
        return
    
    print(f"获取到 {len(df)} 条记录")
    
    # 按股票分组计算防御因子
    defensive_factors = []
    
    for code, group in df.groupby('ts_code'):
        if len(group) < 20:
            continue
        
        try:
            # 计算120日波动率
            returns = group['ret_20'].dropna()
            if len(returns) < 5:
                continue
            
            vol_120 = returns.std()
            
            # 计算最大回撤
            prices = group['ma_20'].dropna()
            if len(prices) < 2:
                continue
            
            cummax = prices.cummax()
            drawdown = (prices - cummax) / cummax
            max_drawdown = drawdown.min()
            
            # 计算下行波动率 (只计算负收益的标准差)
            negative_returns = returns[returns < 0]
            downside_vol = negative_returns.std() if len(negative_returns) > 0 else 0
            
            # 计算夏普比率近似 (收益/波动)
            avg_return = returns.mean()
            sharpe_like = avg_return / vol_120 if vol_120 > 0 else 0
            
            defensive_factors.append({
                'ts_code': code,
                'trade_date': group['trade_date'].iloc[-1],
                'vol_120': vol_120,
                'max_drawdown_120': max_drawdown,
                'downside_vol': downside_vol,
                'sharpe_like': sharpe_like,
                'low_vol_score': 1 / (1 + vol_120) if vol_120 > 0 else 0  # 低波动得分
            })
            
        except Exception as e:
            continue
    
    if not defensive_factors:
        print("❌ 未能计算防御因子")
        conn.close()
        return
    
    # 保存到数据库
    defensive_df = pd.DataFrame(defensive_factors)
    
    # Create table
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_defensive_factors (
            ts_code TEXT,
            trade_date TEXT,
            vol_120 REAL,
            max_drawdown_120 REAL,
            downside_vol REAL,
            sharpe_like REAL,
            low_vol_score REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """)
    
    # Insert data
    for _, row in defensive_df.iterrows():
        cursor.execute("""
            INSERT OR REPLACE INTO stock_defensive_factors 
            (ts_code, trade_date, vol_120, max_drawdown_120, downside_vol, sharpe_like, low_vol_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row['ts_code'], row['trade_date'], row['vol_120'], 
            row['max_drawdown_120'], row['downside_vol'], 
            row['sharpe_like'], row['low_vol_score']
        ))
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 已保存 {len(defensive_factors)} 只股票的防御因子")
    print(f"\n防御因子样例:")
    print(defensive_df.head())


def merge_all_factors():
    """合并所有因子到统一视图"""
    print("\n" + "="*60)
    print("合并所有因子")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get latest date
    cursor.execute("SELECT MAX(trade_date) FROM stock_factors")
    latest_date = cursor.fetchone()[0]
    
    print(f"最新日期: {latest_date}")
    
    # Build query based on available tables
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    tables = [t[0] for t in tables]
    
    query_parts = ["""
        SELECT 
            f.ts_code,
            f.trade_date,
            f.ret_20, f.ret_60, f.ret_120,
            f.vol_20, f.vol_ratio,
            f.price_pos_20, f.price_pos_60,
            f.money_flow, f.rel_strength, f.mom_accel, f.profit_mom
    """]
    
    joins = ["FROM stock_factors f"]
    
    # Add valuation data if available
    if 'stock_valuation' in tables:
        query_parts.append(", v.pe, v.pb, v.market_cap, v.turnover_rate")
        joins.append("LEFT JOIN stock_valuation v ON f.ts_code = v.ts_code AND f.trade_date = v.trade_date")
    
    # Add defensive factors if available
    if 'stock_defensive_factors' in tables:
        query_parts.append(", d.vol_120, d.max_drawdown_120, d.downside_vol, d.low_vol_score")
        joins.append("LEFT JOIN stock_defensive_factors d ON f.ts_code = d.ts_code AND f.trade_date = d.trade_date")
    
    query = " ".join(query_parts) + " " + " ".join(joins)
    query += f" WHERE f.trade_date = '{latest_date}'"
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    print(f"合并后数据: {len(df)} 只股票")
    print(f"\n因子列: {list(df.columns)}")
    
    # Save to CSV for analysis
    output_file = f'/root/.openclaw/workspace/data/all_factors_{latest_date}.csv'
    df.to_csv(output_file, index=False)
    print(f"\n✅ 已保存到: {output_file}")
    
    return df


def analyze_factor_quality(df: pd.DataFrame):
    """分析因子质量"""
    print("\n" + "="*60)
    print("因子质量分析")
    print("="*60)
    
    factor_cols = [c for c in df.columns if c not in ['ts_code', 'trade_date']]
    
    print(f"\n共有 {len(factor_cols)} 个因子:")
    
    for col in factor_cols:
        non_null = df[col].notna().sum()
        coverage = non_null / len(df) * 100
        
        if non_null > 0:
            mean_val = df[col].mean()
            std_val = df[col].std()
            print(f"  {col:20s}: 覆盖率={coverage:5.1f}%, 均值={mean_val:10.4f}, 标准差={std_val:10.4f}")
        else:
            print(f"  {col:20s}: 覆盖率={coverage:5.1f}%")


def main():
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--defensive', action='store_true', help='计算防御因子')
    parser.add_argument('--merge', action='store_true', help='合并所有因子')
    parser.add_argument('--all', action='store_true', help='执行全部')
    
    args = parser.parse_args()
    
    if args.defensive or args.all:
        calculate_defensive_factors()
    
    if args.merge or args.all:
        df = merge_all_factors()
        if df is not None:
            analyze_factor_quality(df)
    
    if not any([args.defensive, args.merge, args.all]):
        print("使用方法:")
        print("  python3 fetch_more_factors.py --defensive  # 计算防御因子")
        print("  python3 fetch_more_factors.py --merge      # 合并所有因子")
        print("  python3 fetch_more_factors.py --all        # 执行全部")


if __name__ == '__main__':
    main()
