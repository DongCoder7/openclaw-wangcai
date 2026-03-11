#!/root/.openclaw/workspace/venv/bin/python3
"""
从历史日线价格计算并补充因子数据 - 改进版
处理年份: 2018-2024
关键改进: 获取前一年的数据用于计算120日收益率
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime
import time

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def calculate_factors(df):
    """计算技术指标因子"""
    if df is None or len(df) < 60:
        return None
    
    df = df.copy()
    df = df.sort_values('trade_date')
    
    # 计算收益率
    df['ret_20'] = df['close'].pct_change(20)
    df['ret_60'] = df['close'].pct_change(60)
    df['ret_120'] = df['close'].pct_change(120)
    
    # 波动率
    df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
    
    # 均线
    df['ma_20'] = df['close'].rolling(20).mean()
    df['ma_60'] = df['close'].rolling(60).mean()
    
    # 趋势位置
    df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min() + 0.001)
    df['price_pos_60'] = (df['close'] - df['low'].rolling(60).min()) / (df['high'].rolling(60).max() - df['low'].rolling(60).min() + 0.001)
    df['price_pos_high'] = (df['close'] - df['high'].rolling(120).max()) / df['close']
    
    # 量比
    df['vol_ratio'] = df['vol'] / df['vol'].rolling(20).mean()
    df['vol_ratio_amt'] = df['vol_ratio']
    
    # 资金流向
    df['money_flow'] = np.where(df['close'] > df['open'], df['vol'], -df['vol'])
    df['money_flow'] = df['money_flow'].rolling(20).sum()
    
    # 相对强度
    df['rel_strength'] = (df['close'] - df['ma_20']) / df['ma_20']
    
    # 动量加速
    df['mom_accel'] = df['ret_20'] - df['ret_20'].shift(20)
    
    # 收益动量
    df['profit_mom'] = df['ret_20'].rolling(20).mean()
    
    return df

def process_stock_year(ts_code, year, cursor):
    """处理单只股票单年的数据"""
    try:
        # 获取该年及前6个月的数据（用于计算120日指标）
        prev_year = str(int(year) - 1)
        
        cursor.execute('''
            SELECT trade_date, open, high, low, close, vol 
            FROM daily_price 
            WHERE ts_code = ? AND (trade_date LIKE ? OR trade_date LIKE ?)
            ORDER BY trade_date
        ''', (ts_code, f'{year}%', f'{prev_year}07%'))
        
        rows = cursor.fetchall()
        if len(rows) < 120:
            return None
        
        df = pd.DataFrame(rows, columns=['trade_date', 'open', 'high', 'low', 'close', 'vol'])
        for col in ['open', 'high', 'low', 'close', 'vol']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 计算因子
        df = calculate_factors(df)
        if df is None or len(df) == 0:
            return None
        
        # 只保留目标年份的数据
        df = df[df['trade_date'].str.startswith(str(year))].copy()
        
        if len(df) == 0:
            return None
        
        # 准备插入数据
        df['ts_code'] = ts_code
        df = df[['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 'vol_20',
                 'vol_ratio', 'vol_ratio_amt', 'ma_20', 'ma_60', 'price_pos_20',
                 'price_pos_60', 'price_pos_high', 'money_flow', 'rel_strength',
                 'mom_accel', 'profit_mom']].copy()
        
        # 删除NaN值
        df = df.dropna()
        
        return df if len(df) > 0 else None
        
    except Exception as e:
        return None

def process_year(year, conn):
    """处理单年的数据"""
    cursor = conn.cursor()
    
    # 获取该年在daily_price中有数据的股票
    cursor.execute('''
        SELECT DISTINCT ts_code FROM daily_price 
        WHERE trade_date LIKE ?
    ''', (f'{year}%',))
    all_stocks = [row[0] for row in cursor.fetchall()]
    
    # 获取该年已有因子数据的股票
    cursor.execute('''
        SELECT DISTINCT ts_code FROM stock_factors 
        WHERE trade_date LIKE ?
    ''', (f'{year}%',))
    existing = set(row[0] for row in cursor.fetchall())
    
    # 需要补充的股票
    to_process = [s for s in all_stocks if s not in existing]
    
    print(f'\n📅 {year}年:')
    print(f'   daily_price有数据: {len(all_stocks)} 只')
    print(f'   已有因子数据: {len(existing)} 只')
    print(f'   需要补充: {len(to_process)} 只')
    
    if len(to_process) == 0:
        return 0
    
    success = 0
    total_rows = 0
    
    for i, ts_code in enumerate(to_process, 1):
        df = process_stock_year(ts_code, year, cursor)
        
        if df is not None and len(df) > 0:
            # 批量插入
            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO stock_factors 
                        (ts_code, trade_date, ret_20, ret_60, ret_120, vol_20,
                         vol_ratio, vol_ratio_amt, ma_20, ma_60, price_pos_20,
                         price_pos_60, price_pos_high, money_flow, rel_strength,
                         mom_accel, profit_mom)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', tuple(row))
                    total_rows += 1
                except:
                    pass
            
            success += 1
        
        if i % 100 == 0:
            print(f'   进度: {i}/{len(to_process)} | 成功: {success} | 记录: {total_rows}')
            conn.commit()
        
        if i % 500 == 0:
            time.sleep(0.5)
    
    conn.commit()
    
    # 统计结果
    cursor.execute('''
        SELECT COUNT(DISTINCT ts_code) FROM stock_factors 
        WHERE trade_date LIKE ?
    ''', (f'{year}%',))
    final_count = cursor.fetchone()[0]
    
    print(f'   ✅ {year}年完成: {final_count} 只股票有因子数据')
    return success

def main():
    print('='*60)
    print('📊 开始补充历史因子数据 (改进版)')
    print('='*60)
    
    conn = sqlite3.connect(DB_PATH)
    
    # 需要处理的年份 (从最近到最远)
    years = [2024, 2023, 2022, 2021, 2020, 2019, 2018]
    
    total_success = 0
    
    for year in years:
        count = process_year(year, conn)
        total_success += count
        time.sleep(2)
    
    conn.close()
    
    print('\n' + '='*60)
    print(f'🎉 全部完成! 共处理 {total_success} 只股票')
    print('='*60)

if __name__ == '__main__':
    main()
