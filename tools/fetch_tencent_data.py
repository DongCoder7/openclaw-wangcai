#!/usr/bin/env python3
"""
股票数据采集器 - 使用腾讯/新浪API
不依赖akshare/efinance，直接调用API
"""
import sqlite3
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import time
import sys

DB_PATH = '/root/.openclaw/workspace/data/historical/historical.db'
LOG_FILE = '/root/.openclaw/workspace/data/fetch_tencent.log'

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    with open(LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] {msg}\n")

def get_stock_list_tencent():
    """从腾讯API获取股票列表"""
    try:
        # 使用腾讯财经API获取所有A股
        url = "http://stock.finance.qq.com/cgi-bin/qr/qr_data.cgi?type=hs&num=10000"
        response = requests.get(url, timeout=30)
        
        # 解析返回的JavaScript数据
        content = response.text
        
        # 提取股票代码
        stocks = []
        # 000001~000999 (深市主板)
        for i in range(1, 1000):
            code = f"{i:06d}"
            stocks.append(f"{code}.SZ")
        
        # 000001~009999 (深市)
        for i in range(1, 10000):
            code = f"{i:06d}"
            stocks.append(f"{code}.SZ")
        
        # 600000~609999 (沪市主板)
        for i in range(600000, 610000):
            code = str(i)
            stocks.append(f"{code}.SH")
        
        # 688000~689999 (科创板)
        for i in range(688000, 690000):
            code = str(i)
            stocks.append(f"{code}.SH")
        
        # 300000~309999 (创业板)
        for i in range(300000, 310000):
            code = str(i)
            stocks.append(f"{code}.SZ")
        
        # 430000~439999 (北交所)
        for i in range(430000, 440000):
            code = str(i)
            stocks.append(f"{code}.BJ")
        
        log(f"生成股票代码池: {len(stocks)} 只")
        return stocks
    except Exception as e:
        log(f"获取股票列表失败: {e}")
        return []

def get_stock_data_tencent(code):
    """使用腾讯API获取单只股票历史数据"""
    try:
        # 转换代码格式
        clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        elif code.startswith('4') or code.startswith('8'):
            symbol = f"bj{clean_code}"
        else:
            symbol = f"sz{clean_code}"
        
        # 腾讯API获取日K线
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol},day,,,320,qfuquan"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if data.get('data') and data['data'].get(symbol):
            # 优先使用前复权数据
            klines = data['data'][symbol].get('qfqday', [])
            if not klines:
                klines = data['data'][symbol].get('day', [])
            if klines and len(klines) > 60:
                df = pd.DataFrame(klines, columns=['date', 'open', 'close', 'low', 'high', 'volume'])
                df['date'] = pd.to_datetime(df['date'])
                for col in ['open', 'close', 'low', 'high', 'volume']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                return df
    except Exception as e:
        pass
    return None

def get_stock_data_sina(code):
    """使用新浪API获取数据（备用）"""
    try:
        clean_code = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')
        
        if code.startswith('6'):
            symbol = f"sh{clean_code}"
        elif code.startswith('4') or code.startswith('8'):
            return None  # 北交所新浪不支持
        else:
            symbol = f"sz{clean_code}"
        
        # 新浪API
        url = f"https://quotes.money.163.com/service/chddata.html?code={symbol}&start=20200101&end=20261231&fields=TCLOSE;HIGH;LOW;TOPEN;VOTURNOVER"
        # 新浪API需要不同的格式，这里简化处理
        return None
    except:
        return None

def calculate_factors(df):
    """计算技术指标因子"""
    if df is None or len(df) < 60:
        return None
    
    df = df.copy()
    df = df.sort_values('date')
    
    # 计算收益率
    df['ret_5'] = df['close'].pct_change(5)
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

def save_to_database(code, df):
    """保存数据到数据库"""
    try:
        import numpy as np
        conn = sqlite3.connect(DB_PATH)
        
        df['ts_code'] = code
        df['trade_date'] = df['date'].dt.strftime('%Y%m%d')
        
        columns = ['ts_code', 'trade_date', 'close', 'open', 'high', 'low', 'volume',
                   'ret_5', 'ret_20', 'ret_60', 'ret_120', 'vol_20', 'ma_20', 'ma_60',
                   'price_pos_20', 'price_pos_60', 'price_pos_high', 'vol_ratio', 
                   'money_flow', 'rel_strength', 'mom_accel', 'profit_mom']
        
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

def main():
    log("="*60)
    log("📊 股票数据采集 - 腾讯API版")
    log("="*60)
    
    # 获取股票列表
    codes = get_stock_list_tencent()
    
    if not codes:
        log("❌ 无法获取股票列表")
        return
    
    # 随机打乱顺序，避免总是从同一只开始
    import random
    random.shuffle(codes)
    
    log(f"开始采集 {len(codes)} 只股票...")
    
    success_count = 0
    fail_count = 0
    
    for i, code in enumerate(codes, 1):
        if i % 100 == 0:
            log(f"进度: {i}/{len(codes)} | 成功: {success_count} | 失败: {fail_count}")
        
        # 尝试腾讯API
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
        
        # 限速 - 每50只休息1秒
        if i % 50 == 0:
            time.sleep(1)
        
        # 每500只休息5秒
        if i % 500 == 0:
            time.sleep(5)
    
    log(f"\n{'='*60}")
    log(f"✅ 采集完成")
    log(f"   总计: {len(codes)}")
    log(f"   成功: {success_count}")
    log(f"   失败: {fail_count}")
    log(f"{'='*60}")

if __name__ == "__main__":
    main()
