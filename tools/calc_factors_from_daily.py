#!/usr/bin/env python3
"""
从daily_price计算stock_factors (2022-2024)
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/calc_factors_2022_2024.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def calculate_factors_for_stock(df):
    """计算单只股票因子"""
    if len(df) < 60:
        return None
    
    df = df.sort_values('trade_date').copy()
    
    # 收益率
    df['ret_20'] = df['close'].pct_change(20)
    df['ret_60'] = df['close'].pct_change(60)
    df['ret_120'] = df['close'].pct_change(120)
    
    # 波动率
    df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
    
    # 均线
    df['ma_20'] = df['close'].rolling(20).mean()
    df['ma_60'] = df['close'].rolling(60).mean()
    
    # 价格位置
    df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
    df['price_pos_60'] = (df['close'] - df['low'].rolling(60).min()) / (df['high'].rolling(60).max() - df['low'].rolling(60).min() + 0.001)
    df['price_pos_high'] = (df['close'] - df['high'].rolling(120).max()) / df['close']
    
    # 量比
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['vol_ratio_amt'] = df['vol_ratio']
    
    # 资金流向
    df['money_flow'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
    df['money_flow'] = df['money_flow'].rolling(20).sum()
    
    # 相对强度
    df['rel_strength'] = (df['close'] - df['ma_20']) / df['ma_20']
    
    # 动量加速
    df['mom_accel'] = df['ret_20'] - df['ret_20'].shift(20)
    
    # 收益动量
    df['profit_mom'] = df['ret_20'].rolling(20).mean()
    
    return df

def main():
    log("="*70)
    log("🚀 从daily_price计算stock_factors (2022-2024)")
    log("="*70)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 获取有daily_price数据的股票列表
    stocks = conn.execute('''
        SELECT DISTINCT ts_code FROM daily_price 
        WHERE trade_date BETWEEN "20220101" AND "20241231"
    ''').fetchall()
    
    stocks = [s[0] for s in stocks]
    log(f"需要处理的股票: {len(stocks)}只")
    
    success_count = 0
    fail_count = 0
    
    for i, ts_code in enumerate(stocks, 1):
        if i % 100 == 0:
            log(f"进度: {i}/{len(stocks)} | 成功: {success_count} | 失败: {fail_count}")
        
        # 获取日线数据
        rows = conn.execute('''
            SELECT trade_date, open, high, low, close, volume
            FROM daily_price
            WHERE ts_code = ? AND trade_date BETWEEN "20220101" AND "20241231"
            ORDER BY trade_date
        ''', [ts_code]).fetchall()
        
        if len(rows) < 60:
            fail_count += 1
            continue
        
        # 转为DataFrame
        df = pd.DataFrame(rows, columns=['trade_date', 'open', 'high', 'low', 'close', 'volume'])
        
        # 计算因子
        df = calculate_factors_for_stock(df)
        if df is None:
            fail_count += 1
            continue
        
        # 准备保存的数据
        df['ts_code'] = ts_code
        
        # 选择列
        columns = ['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 'vol_20', 
                   'vol_ratio', 'vol_ratio_amt', 'ma_20', 'ma_60', 'price_pos_20', 
                   'price_pos_60', 'price_pos_high', 'money_flow', 'rel_strength', 
                   'mom_accel', 'profit_mom']
        
        df_save = df[columns].dropna()
        
        if len(df_save) == 0:
            fail_count += 1
            continue
        
        # 删除旧数据并插入新数据
        try:
            conn.execute("DELETE FROM stock_factors WHERE ts_code = ? AND trade_date BETWEEN '20220101' AND '20241231'", [ts_code])
            df_save.to_sql('stock_factors', conn, if_exists='append', index=False)
            success_count += 1
        except Exception as e:
            log(f"保存失败 {ts_code}: {str(e)[:50]}")
            fail_count += 1
    
    conn.commit()
    conn.close()
    
    log(f"\n{'='*70}")
    log("✅ 计算完成")
    log(f"  成功: {success_count}")
    log(f"  失败: {fail_count}")
    log(f"{'='*70}")

if __name__ == '__main__':
    main()
