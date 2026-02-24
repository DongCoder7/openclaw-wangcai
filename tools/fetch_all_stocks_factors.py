#!/usr/bin/env python3
"""
全市场股票数据采集器 - 使用腾讯API
直接调用腾讯API，不依赖第三方库
"""
import sqlite3
import pandas as pd
import requests
from datetime import datetime, timedelta
import time
import sys
import os

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/fetch_tencent.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_stock_data_tencent(code):
    """使用腾讯API获取单只股票历史数据"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        elif code.startswith('4') or code.startswith('8'):
            symbol = f"bj{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfuquan"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data.get('data') and data['data'].get(symbol):
            klines = data['data'][symbol].get('qfqday', []) or data['data'][symbol].get('day', [])
            if klines and len(klines) >= 60:
                # 过滤掉列数不对的数据
                valid_data = [row for row in klines if len(row) == 6]
                if len(valid_data) >= 60:
                    df = pd.DataFrame(valid_data, columns=['date', 'open', 'close', 'low', 'high', 'volume'])
                    df['date'] = pd.to_datetime(df['date'])
                    for col in ['open', 'close', 'low', 'high', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
    except Exception as e:
        pass
    return None

def calculate_factors(df):
    """计算技术指标因子"""
    if df is None or len(df) < 60:
        return None
    
    df = df.copy()
    df = df.sort_values('date')
    
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
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['vol_ratio_amt'] = df['vol_ratio']  # 兼容旧字段
    
    # 资金流向
    import numpy as np
    df['money_flow'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
    df['money_flow'] = df['money_flow'].rolling(20).sum()
    
    # 相对强度
    df['rel_strength'] = (df['close'] - df['ma_20']) / df['ma_20']
    
    # 动量加速
    df['mom_accel'] = df['ret_20'] - df['ret_20'].shift(20)
    
    # 收益动量
    df['profit_mom'] = df['ret_20'].rolling(20).mean()
    
    return df

def save_to_database(code, df):
    """保存数据到数据库"""
    try:
        import numpy as np
        conn = sqlite3.connect(DB_PATH)
        
        df['ts_code'] = code
        df['trade_date'] = df['date'].dt.strftime('%Y%m%d')
        
        # 只保存数据库表结构支持的列
        columns = ['ts_code', 'trade_date', 'ret_20', 'ret_60', 'ret_120', 'vol_20', 
                   'vol_ratio', 'vol_ratio_amt', 'ma_20', 'ma_60', 'price_pos_20', 
                   'price_pos_60', 'price_pos_high', 'money_flow', 'rel_strength', 
                   'mom_accel', 'profit_mom']
        
        available_cols = [c for c in columns if c in df.columns]
        df_to_save = df[available_cols].copy()
        
        # 删除NaN值
        df_to_save = df_to_save.dropna()
        
        if len(df_to_save) == 0:
            return False
        
        # 删除旧数据
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM stock_factors WHERE ts_code = '{code}'")
        
        # 插入新数据
        df_to_save.to_sql('stock_factors', conn, if_exists='append', index=False)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f"保存{code}失败: {e}")
        return False

def generate_stock_codes():
    """生成A股股票代码列表"""
    codes = []
    
    # 000001-009999 (深市主板)
    for i in range(1, 10000):
        codes.append(f"{i:06d}.SZ")
    
    # 300000-309999 (创业板)
    for i in range(300000, 310000):
        codes.append(f"{i}.SZ")
    
    # 600000-609999 (沪市主板)
    for i in range(600000, 610000):
        codes.append(f"{i}.SH")
    
    # 688000-689999 (科创板)
    for i in range(688000, 690000):
        codes.append(f"{i}.SH")
    
    # 430000-439999 (北交所)
    for i in range(430000, 440000):
        codes.append(f"{i}.BJ")
    
    import random
    random.shuffle(codes)
    
    return codes

def main():
    log("="*60)
    log("📊 全市场数据采集 - 腾讯API")
    log("="*60)
    
    codes = generate_stock_codes()
    log(f"股票代码池: {len(codes)} 只")
    
    success_count = 0
    fail_count = 0
    
    for i, code in enumerate(codes, 1):
        if i % 100 == 0:
            log(f"进度: {i}/{len(codes)} | 成功: {success_count} | 失败: {fail_count}")
        
        # 获取数据
        df = get_stock_data_tencent(code)
        
        if df is None:
            fail_count += 1
            continue
        
        # 计算因子
        df = calculate_factors(df)
        if df is None:
            fail_count += 1
            continue
        
        # 保存
        if save_to_database(code, df):
            success_count += 1
        else:
            fail_count += 1
        
        # 限速
        if i % 50 == 0:
            time.sleep(0.5)
        if i % 500 == 0:
            time.sleep(2)
    
    log(f"\n{'='*60}")
    log(f"✅ 采集完成")
    log(f"   总计: {len(codes)}")
    log(f"   成功: {success_count}")
    log(f"   失败: {fail_count}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
