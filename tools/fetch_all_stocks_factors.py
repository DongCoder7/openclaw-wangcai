#!/usr/bin/env python3
"""
全市场股票因子采集器
采集A股全市场5000+只股票的因子数据
"""
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import akshare as ak
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'

def get_all_stock_codes():
    """获取全市场所有A股代码"""
    try:
        # 使用akshare获取全市场股票
        df = ak.stock_zh_a_spot_em()
        codes = []
        for _, row in df.iterrows():
            code = row['代码']
            # 统一格式
            if code.startswith('6'):
                codes.append(f"{code}.SH")
            else:
                codes.append(f"{code}.SZ")
        print(f"获取到 {len(codes)} 只A股")
        return codes
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []

def fetch_stock_data(code):
    """获取单只股票的日K数据"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '')
        df = ak.stock_zh_a_hist(symbol=clean_code, period="daily", 
                                 start_date="20240101", end_date="20250224", adjust="qfq")
        return df
    except Exception as e:
        print(f"  获取{code}数据失败: {e}")
        return None

def calculate_factors(df):
    """计算技术指标因子"""
    if df is None or len(df) < 60:
        return None
    
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    
    # 确保必要列存在
    required_cols = ['close', 'open', 'high', 'low', 'volume']
    for col in required_cols:
        if col not in df.columns:
            return None
    
    # 计算技术指标
    # 1. 收益率
    df['ret_5'] = df['close'].pct_change(5)
    df['ret_20'] = df['close'].pct_change(20)
    df['ret_60'] = df['close'].pct_change(60)
    
    # 2. 波动率
    df['vol_20'] = df['close'].rolling(20).std() / df['close'].rolling(20).mean()
    
    # 3. 均线
    df['ma_5'] = df['close'].rolling(5).mean()
    df['ma_20'] = df['close'].rolling(20).mean()
    df['ma_60'] = df['close'].rolling(60).mean()
    
    # 4. 趋势位置
    df['price_pos_20'] = (df['close'] - df['low'].rolling(20).min()) / (df['high'].rolling(20).max() - df['low'].rolling(20).min())
    df['price_pos_60'] = (df['close'] - df['low'].rolling(60).min()) / (df['high'].rolling(60).max() - df['low'].rolling(60).min())
    
    # 5. 资金流向 (简化版)
    df['money_flow'] = np.where(df['close'] > df['open'], df['volume'], -df['volume'])
    df['money_flow'] = df['money_flow'].rolling(20).sum()
    
    # 6. 动量加速
    df['mom_accel'] = df['ret_20'] - df['ret_20'].shift(20)
    
    # 7. 相对强度 (vs 20日均线)
    df['rel_strength'] = (df['close'] - df['ma_20']) / df['ma_20']
    
    return df

def save_to_database(code, df):
    """保存数据到数据库"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 准备数据
        df['ts_code'] = code
        df['trade_date'] = df['日期'].str.replace('-', '') if '日期' in df.columns else df.index.strftime('%Y%m%d')
        
        # 选择需要的列
        columns = ['ts_code', 'trade_date', 'close', 'open', 'high', 'low', 'volume',
                   'ret_5', 'ret_20', 'ret_60', 'vol_20', 'ma_5', 'ma_20', 'ma_60',
                   'price_pos_20', 'price_pos_60', 'money_flow', 'mom_accel', 'rel_strength']
        
        available_cols = [c for c in columns if c in df.columns]
        df_to_save = df[available_cols].copy()
        
        # 删除旧数据
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM stock_factors WHERE ts_code = '{code}'")
        
        # 插入新数据
        df_to_save.to_sql('stock_factors', conn, if_exists='append', index=False)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"  保存{code}数据失败: {e}")
        return False

def main():
    print("="*60)
    print("📊 全市场股票因子采集")
    print("="*60)
    
    # 获取所有股票代码
    codes = get_all_stock_codes()
    if not codes:
        print("❌ 获取股票列表失败")
        return
    
    print(f"\n开始采集 {len(codes)} 只股票的因子数据...")
    
    success_count = 0
    fail_count = 0
    
    for i, code in enumerate(codes, 1):
        print(f"\n[{i}/{len(codes)}] 处理 {code}...")
        
        # 获取数据
        df = fetch_stock_data(code)
        if df is None:
            fail_count += 1
            continue
        
        # 计算因子
        df = calculate_factors(df)
        if df is None:
            print(f"  数据不足，跳过")
            fail_count += 1
            continue
        
        # 保存
        if save_to_database(code, df):
            print(f"  ✅ 成功")
            success_count += 1
        else:
            fail_count += 1
        
        # 每100只显示进度
        if i % 100 == 0:
            print(f"\n📈 进度: {i}/{len(codes)} | 成功: {success_count} | 失败: {fail_count}")
    
    print(f"\n{'='*60}")
    print(f"✅ 采集完成")
    print(f"   总计: {len(codes)}")
    print(f"   成功: {success_count}")
    print(f"   失败: {fail_count}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
