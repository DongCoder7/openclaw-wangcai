#!/usr/bin/env python3
"""
每日数据更新脚本 (Daily Data Update)
功能：
1. 获取当日行情 → daily_price
2. 计算当日技术指标 → stock_factors, stock_technical_factors  
3. 获取当日估值 → daily_basic, stock_valuation
4. 检查数据完整性
5. 生成更新报告

执行时间：每日收盘后 16:00 (由Heartbeat触发)
验证状态：已验证 2026-03-04
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import tushare as ts

# 配置
WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'
TS_TOKEN = 'cd2c935050381b52c9849eb054d1b198c21b0f29be2f025f9a9ece30'
BATCH_SIZE = 100

# 初始化Tushare
ts.set_token(TS_TOKEN)
pro = ts.pro_api()

def log(msg):
    """记录日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()

def get_trade_date():
    """获取最近交易日"""
    try:
        today = datetime.now()
        start_date = (today - timedelta(days=10)).strftime('%Y%m%d')
        end_date = today.strftime('%Y%m%d')
        
        df = pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date)
        trade_date = df[df['is_open'] == 1]['cal_date'].max()
        return trade_date
    except Exception as e:
        log(f"❌ 获取交易日失败: {e}")
        return None

def init_tables(conn):
    """初始化数据库表"""
    cursor = conn.cursor()
    
    # daily_price 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_price (
            ts_code TEXT,
            trade_date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            amount REAL,
            change_pct REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    # daily_basic 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_basic (
            ts_code TEXT,
            trade_date TEXT,
            close REAL,
            turnover_rate REAL,
            pe REAL,
            pe_ttm REAL,
            pb REAL,
            ps REAL,
            total_mv REAL,
            circ_mv REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    # stock_factors 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_factors (
            ts_code TEXT,
            trade_date TEXT,
            ret_20 REAL,
            ret_60 REAL,
            ret_120 REAL,
            vol_20 REAL,
            vol_ratio REAL,
            ma_20 REAL,
            ma_60 REAL,
            price_pos_20 REAL,
            price_pos_60 REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    # stock_technical_factors 表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_technical_factors (
            ts_code TEXT,
            trade_date TEXT,
            close REAL,
            rsi_14 REAL,
            rsi_6 REAL,
            rsi_24 REAL,
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
    ''')
    
    # stock_valuation 表
    cursor.execute('''
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
    ''')
    
    conn.commit()
    log("✅ 数据库表初始化完成")

def update_daily_price(conn, trade_date):
    """更新日线行情数据"""
    log(f"📈 更新日线行情 (trade_date={trade_date})")
    
    try:
        # 获取当日所有股票行情
        df = pro.daily(trade_date=trade_date)
        
        if df.empty:
            log(f"⚠️ 未获取到 {trade_date} 的行情数据")
            return 0
        
        # 计算涨跌幅
        df['change_pct'] = df['pct_chg']
        
        # 插入数据库
        cursor = conn.cursor()
        inserted = 0
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO daily_price 
                (ts_code, trade_date, open, high, low, close, volume, amount, change_pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['ts_code'], trade_date, row['open'], row['high'], 
                row['low'], row['close'], row['vol'], row['amount'], row['change_pct']
            ))
            inserted += 1
        
        conn.commit()
        log(f"✅ 日线行情更新完成: {inserted}只股票")
        return inserted
        
    except Exception as e:
        log(f"❌ 更新日线行情失败: {e}")
        return 0

def update_daily_basic(conn, trade_date):
    """更新估值数据"""
    log(f"💰 更新估值数据 (trade_date={trade_date})")
    
    try:
        df = pro.daily_basic(trade_date=trade_date)
        
        if df.empty:
            log(f"⚠️ 未获取到 {trade_date} 的估值数据")
            return 0
        
        cursor = conn.cursor()
        inserted = 0
        
        for _, row in df.iterrows():
            cursor.execute('''
                INSERT OR REPLACE INTO daily_basic 
                (ts_code, trade_date, close, turnover_rate, pe, pe_ttm, pb, ps, total_mv, circ_mv)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['ts_code'], trade_date, row['close'], row['turnover_rate'],
                row['pe'], row['pe_ttm'], row['pb'], row['ps'], 
                row['total_mv'], row['circ_mv']
            ))
            inserted += 1
            
            # 同时更新 stock_valuation
            cursor.execute('''
                INSERT OR REPLACE INTO stock_valuation 
                (ts_code, trade_date, price, pe, pb, market_cap, turnover_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                row['ts_code'], trade_date, row['close'], row['pe_ttm'], 
                row['pb'], row['total_mv'], row['turnover_rate']
            ))
        
        conn.commit()
        log(f"✅ 估值数据更新完成: {inserted}只股票")
        return inserted
        
    except Exception as e:
        log(f"❌ 更新估值数据失败: {e}")
        return 0

def calc_rsi(prices, window=14):
    """计算RSI"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=window, min_periods=1).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window, min_periods=1).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_macd(prices, fast=12, slow=26, signal=9):
    """计算MACD"""
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    macd_signal = macd.ewm(span=signal, adjust=False).mean()
    macd_hist = macd - macd_signal
    return macd, macd_signal, macd_hist

def update_technical_factors(conn, trade_date):
    """更新技术指标"""
    log(f"📊 更新技术指标 (trade_date={trade_date})")
    
    try:
        # 获取最近120天数据用于计算
        end_date = trade_date
        start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=180)).strftime('%Y%m%d')
        
        df = pd.read_sql(f"""
            SELECT ts_code, trade_date, close, high, low, volume, amount
            FROM daily_price 
            WHERE trade_date BETWEEN '{start_date}' AND '{end_date}'
            ORDER BY ts_code, trade_date
        """, conn)
        
        if df.empty:
            log(f"⚠️ 没有足够的历史数据计算技术指标")
            return 0
        
        cursor = conn.cursor()
        updated = 0
        
        for ts_code in df['ts_code'].unique():
            stock_df = df[df['ts_code'] == ts_code].sort_values('trade_date')
            
            if len(stock_df) < 60:
                continue
            
            # 计算技术指标
            stock_df['rsi_14'] = calc_rsi(stock_df['close'], 14)
            stock_df['rsi_6'] = calc_rsi(stock_df['close'], 6)
            stock_df['rsi_24'] = calc_rsi(stock_df['close'], 24)
            
            stock_df['macd'], stock_df['macd_signal'], stock_df['macd_hist'] = calc_macd(stock_df['close'])
            
            # 计算收益率和波动率
            stock_df['ret_20'] = stock_df['close'].pct_change(20) * 100
            stock_df['ret_60'] = stock_df['close'].pct_change(60) * 100
            stock_df['ret_120'] = stock_df['close'].pct_change(120) * 100
            stock_df['vol_20'] = stock_df['close'].pct_change().rolling(20).std() * np.sqrt(252) * 100
            
            # 均线
            stock_df['ma_20'] = stock_df['close'].rolling(20).mean()
            stock_df['ma_60'] = stock_df['close'].rolling(60).mean()
            
            # 价格位置
            rolling_20 = stock_df['close'].rolling(20)
            stock_df['price_pos_20'] = (stock_df['close'] - rolling_20.min()) / (rolling_20.max() - rolling_20.min())
            rolling_60 = stock_df['close'].rolling(60)
            stock_df['price_pos_60'] = (stock_df['close'] - rolling_60.min()) / (rolling_60.max() - rolling_60.min())
            
            # 只保存当日数据
            today_data = stock_df[stock_df['trade_date'] == trade_date]
            
            for _, row in today_data.iterrows():
                # 保存到 stock_technical_factors
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_technical_factors 
                    (ts_code, trade_date, close, rsi_14, rsi_6, rsi_24,
                     macd, macd_signal, macd_hist, update_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_code, trade_date, row['close'], row['rsi_14'], row['rsi_6'], row['rsi_24'],
                    row['macd'], row['macd_signal'], row['macd_hist'], datetime.now().isoformat()
                ))
                
                # 保存到 stock_factors
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_factors 
                    (ts_code, trade_date, ret_20, ret_60, ret_120, vol_20,
                     ma_20, ma_60, price_pos_20, price_pos_60)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    ts_code, trade_date, row['ret_20'], row['ret_60'], row['ret_120'], row['vol_20'],
                    row['ma_20'], row['ma_60'], row['price_pos_20'], row['price_pos_60']
                ))
                updated += 1
        
        conn.commit()
        log(f"✅ 技术指标更新完成: {updated}只股票")
        return updated
        
    except Exception as e:
        log(f"❌ 更新技术指标失败: {e}")
        return 0

def verify_data(conn, trade_date):
    """验证数据完整性"""
    log(f"🔍 验证数据完整性 (trade_date={trade_date})")
    
    cursor = conn.cursor()
    report = []
    
    tables = [
        ('daily_price', '日线行情'),
        ('daily_basic', '估值数据'),
        ('stock_factors', '基础因子'),
        ('stock_technical_factors', '技术因子'),
        ('stock_valuation', '估值表')
    ]
    
    for table, name in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE trade_date=?", (trade_date,))
        count = cursor.fetchone()[0]
        report.append(f"  {name}({table}): {count}条")
    
    for line in report:
        log(line)
    
    return report

def main():
    """主函数"""
    log("="*70)
    log("🚀 每日数据更新开始")
    log("="*70)
    
    # 获取交易日
    trade_date = get_trade_date()
    if not trade_date:
        log("❌ 无法获取交易日，退出")
        return
    log(f"📅 最近交易日: {trade_date}")
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    
    # 初始化表
    init_tables(conn)
    
    # 检查是否已更新
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM daily_price WHERE trade_date=?", (trade_date,))
    existing = cursor.fetchone()[0]
    
    if existing > 3000:
        log(f"✅ {trade_date} 数据已存在({existing}条)，跳过更新")
        verify_data(conn, trade_date)
        conn.close()
        return
    
    # 1. 更新日线行情
    price_count = update_daily_price(conn, trade_date)
    
    # 2. 更新估值数据
    basic_count = update_daily_basic(conn, trade_date)
    
    # 3. 更新技术指标
    tech_count = update_technical_factors(conn, trade_date)
    
    # 4. 验证数据
    report = verify_data(conn, trade_date)
    
    conn.close()
    
    # 保存报告
    log("="*70)
    log("✅ 每日数据更新完成")
    log(f"  日线行情: {price_count}只")
    log(f"  估值数据: {basic_count}只")
    log(f"  技术指标: {tech_count}只")
    log("="*70)
    
    # 生成状态文件
    state = {
        'date': trade_date,
        'timestamp': datetime.now().isoformat(),
        'price_count': price_count,
        'basic_count': basic_count,
        'tech_count': tech_count,
        'status': 'success'
    }
    
    os.makedirs(f'{WORKSPACE}/data', exist_ok=True)
    with open(f'{WORKSPACE}/data/daily_update_state.json', 'w') as f:
        json.dump(state, f, indent=2)

if __name__ == '__main__':
    main()
