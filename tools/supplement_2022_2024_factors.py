#!/usr/bin/env python3
"""
紧急补充2022-2024年stock_factors数据
使用腾讯API获取历史数据
"""
import sqlite3
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/supplement_2022_2024.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_stock_list():
    """获取股票列表"""
    conn = sqlite3.connect(DB_PATH)
    stocks = conn.execute('SELECT DISTINCT ts_code FROM stock_basic').fetchall()
    conn.close()
    return [s[0] for s in stocks]

def get_tencent_data(symbol, start_date, end_date):
    """从腾讯API获取历史数据"""
    try:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,{start_date},{end_date},500,qfuquan"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('data') and data['data'].get(symbol):
            klines = data['data'][symbol].get('qfqday', []) or data['data'][symbol].get('day', [])
            if klines:
                df = pd.DataFrame(klines, columns=['date', 'open', 'close', 'low', 'high', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                for col in ['open', 'close', 'low', 'high', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
    except Exception as e:
        pass
    return None

def calculate_factors(df):
    """计算因子"""
    if df is None or len(df) < 60:
        return None
    
    df = df.sort_values('date').copy()
    
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

def save_to_db(ts_code, df):
    """保存到数据库"""
    if df is None or len(df) == 0:
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        
        df['ts_code'] = ts_code
        df['trade_date'] = df['date'].dt.strftime('%Y%m%d')
        
        # 选择需要的列
        columns = ['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 'vol_20', 
                   'vol_ratio', 'ma_20', 'ma_60', 'price_pos_20', 'price_pos_60', 'price_pos_high', 
                   'money_flow', 'rel_strength', 'mom_accel', 'profit_mom']
        
        available_cols = [c for c in columns if c in df.columns]
        df_to_save = df[available_cols].copy()
        df_to_save = df_to_save.dropna()
        
        if len(df_to_save) == 0:
            return False
        
        # 删除旧数据
        conn.execute(f"DELETE FROM stock_factors WHERE ts_code = '{ts_code}' AND trade_date BETWEEN '20220101' AND '20241231'")
        
        # 插入新数据
        df_to_save.to_sql('stock_factors', conn, if_exists='append', index=False)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"保存失败 {ts_code}: {str(e)[:100]}")
        return False

def main():
    log("="*70)
    log("🚀 紧急补充2022-2024年stock_factors数据")
    log("="*70)
    
    # 获取股票列表
    stocks = get_stock_list()
    log(f"股票总数: {len(stocks)}")
    
    # 年份范围
    years = [
        ('20220101', '20221231', '2022'),
        ('20230101', '20231231', '2023'),
        ('20240101', '20241231', '2024')
    ]
    
    total_success = 0
    total_fail = 0
    
    for year_start, year_end, year_name in years:
        log(f"\n{'='*70}")
        log(f"📅 开始补充 {year_name} 年数据")
        log(f"{'='*70}")
        
        year_success = 0
        year_fail = 0
        
        for i, ts_code in enumerate(stocks, 1):
            if i % 100 == 0:
                log(f"  进度: {i}/{len(stocks)} | 成功: {year_success} | 失败: {year_fail}")
            
            # 转换代码
            clean_code = ts_code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
            if ts_code.startswith('6'):
                symbol = f"sh{clean_code}"
            elif ts_code.startswith('4') or ts_code.startswith('8'):
                symbol = f"bj{clean_code}"
            else:
                symbol = f"sz{clean_code}"
            
            # 获取数据
            df = get_tencent_data(symbol, year_start, year_end)
            
            if df is None:
                year_fail += 1
                continue
            
            # 计算因子
            df = calculate_factors(df)
            if df is None:
                year_fail += 1
                continue
            
            # 保存
            if save_to_db(ts_code, df):
                year_success += 1
            else:
                year_fail += 1
            
            # 限速
            if i % 50 == 0:
                time.sleep(0.5)
            if i % 200 == 0:
                time.sleep(2)
        
        log(f"\n{year_name}年完成:")
        log(f"  成功: {year_success}")
        log(f"  失败: {year_fail}")
        
        total_success += year_success
        total_fail += year_fail
    
    log(f"\n{'='*70}")
    log("✅ 数据补充完成")
    log(f"  总成功: {total_success}")
    log(f"  总失败: {total_fail}")
    log(f"{'='*70}")

if __name__ == '__main__':
    main()
