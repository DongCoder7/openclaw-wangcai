#!/usr/bin/env python3
"""
多因子数据补充 - 分批次处理2018-2021年缺口
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
LOG_PATH = f'{WORKSPACE}/reports/supplement_factors_batch.log'
BATCH_SIZE = 300

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_PATH, 'a') as f:
        f.write(line + '\n')

def get_pending_stocks():
    """获取缺少2018年多因子数据的股票"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT ts_code FROM daily_price 
        WHERE trade_date BETWEEN '20180101' AND '20181231'
        AND ts_code NOT IN (
            SELECT DISTINCT ts_code FROM stock_factors 
            WHERE trade_date BETWEEN '20180101' AND '20181231'
        )
        LIMIT ?
    """, (BATCH_SIZE,))
    stocks = [r[0] for r in cursor.fetchall()]
    
    # 获取总数
    cursor.execute("""
        SELECT COUNT(DISTINCT ts_code) FROM daily_price 
        WHERE trade_date BETWEEN '20180101' AND '20181231'
        AND ts_code NOT IN (
            SELECT DISTINCT ts_code FROM stock_factors 
            WHERE trade_date BETWEEN '20180101' AND '20181231'
        )
    """)
    remaining = cursor.fetchone()[0]
    conn.close()
    return stocks, remaining

def calc_factors(prices, volumes):
    """计算技术指标因子"""
    factors = {}
    
    if len(prices) < 20:
        return None
    
    # 价格相关
    factors['ma_20'] = prices[-20:].mean()
    factors['ma_60'] = prices[-60:].mean() if len(prices) >= 60 else prices.mean()
    
    # 价格位置
    high_20 = prices[-20:].max()
    low_20 = prices[-20:].min()
    factors['price_pos_20'] = (prices[-1] - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5
    
    high_60 = prices[-60:].max() if len(prices) >= 60 else prices.max()
    low_60 = prices[-60:].min() if len(prices) >= 60 else prices.min()
    factors['price_pos_60'] = (prices[-1] - low_60) / (high_60 - low_60) if high_60 != low_60 else 0.5
    
    # 收益率
    factors['ret_20'] = (prices[-1] - prices[-20]) / prices[-20] if prices[-20] != 0 else 0
    factors['ret_60'] = (prices[-1] - prices[-60]) / prices[-60] if len(prices) >= 60 and prices[-60] != 0 else 0
    factors['ret_120'] = (prices[-1] - prices[-120]) / prices[-120] if len(prices) >= 120 and prices[-120] != 0 else 0
    
    # 波动率
    returns = prices.pct_change().dropna()
    factors['vol_20'] = returns[-20:].std() * np.sqrt(252) if len(returns) >= 20 else 0
    
    # 成交量比
    if len(volumes) >= 20:
        factors['vol_ratio'] = volumes[-1] / volumes[-20:].mean() if volumes[-20:].mean() != 0 else 1
    else:
        factors['vol_ratio'] = 1
    
    return factors

def supplement_batch(stocks):
    """处理一批股票的多因子"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_records = 0
    
    for i, ts_code in enumerate(stocks):
        if i % 50 == 0:
            log(f"  进度: {i}/{len(stocks)} | 累计:{total_records}")
        
        try:
            # 获取日线数据
            df = pd.read_sql(f"""
                SELECT trade_date, close, volume 
                FROM daily_price 
                WHERE ts_code='{ts_code}' AND trade_date BETWEEN '20170101' AND '20211231'
                ORDER BY trade_date
            """, conn)
            
            if len(df) < 60:
                continue
            
            df['trade_date'] = pd.to_datetime(df['trade_date'])
            df = df.sort_values('trade_date')
            
            # 为每个交易日计算因子
            for idx in range(60, len(df)):
                date_str = df.iloc[idx]['trade_date'].strftime('%Y%m%d')
                prices = df['close'].iloc[:idx+1]
                volumes = df['volume'].iloc[:idx+1]
                
                # 只补充2018-2021年的数据
                if not (20180101 <= int(date_str) <= 20211231):
                    continue
                
                # 检查是否已存在
                cursor.execute("SELECT 1 FROM stock_factors WHERE ts_code=? AND trade_date=?", 
                              (ts_code, date_str))
                if cursor.fetchone():
                    continue
                
                factors = calc_factors(prices, volumes)
                if factors:
                    cursor.execute('''
                        INSERT INTO stock_factors 
                        (ts_code, trade_date, ret_20, ret_60, ret_120, vol_20, vol_ratio, 
                         ma_20, ma_60, price_pos_20, price_pos_60)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    ''', (
                        ts_code, date_str, 
                        factors.get('ret_20'), factors.get('ret_60'), factors.get('ret_120'),
                        factors.get('vol_20'), factors.get('vol_ratio'),
                        factors.get('ma_20'), factors.get('ma_60'),
                        factors.get('price_pos_20'), factors.get('price_pos_60')
                    ))
                    total_records += 1
            
            # 每只股票提交一次
            if i % 10 == 0:
                conn.commit()
                
        except Exception as e:
            continue
    
    conn.commit()
    conn.close()
    return total_records

def main():
    with open(LOG_PATH, 'a') as f:
        f.write(f"\n[{datetime.now()}] 多因子批次开始\n")
    
    log("="*50)
    log("多因子数据补充 (2018-2021)")
    log("="*50)
    
    stocks, remaining = get_pending_stocks()
    log(f"本批次处理: {len(stocks)}只, 剩余缺口: {remaining}只")
    
    if len(stocks) == 0:
        log("✅ 所有股票多因子数据已补充完成!")
        return
    
    records = supplement_batch(stocks)
    
    log(f"✅ 本批次完成! 新增多因子记录: {records}条")
    log(f"剩余待处理: {remaining - len(stocks)}只")
    log("="*50)

if __name__ == '__main__':
    main()
