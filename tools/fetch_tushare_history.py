#!/usr/bin/env python3
"""
Tushare历史因子回补脚本 (2018-2026)
批量获取历史估值因子和技术指标
"""

import sys
import os
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple
import tushare as ts
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

WORKSPACE = '/root/.openclaw/workspace'
DB_PATH = f'{WORKSPACE}/data/historical/historical.db'

class TushareHistoryFetcher:
    """Tushare历史数据获取器"""
    
    def __init__(self):
        self.pro = self._init_tushare()
        self.conn = sqlite3.connect(DB_PATH)
        
    def _init_tushare(self):
        """初始化Tushare"""
        token = ''
        env_file = f'{WORKSPACE}/.tushare.env'
        if os.path.exists(env_file):
            with open(env_file, 'r') as f:
                for line in f:
                    if 'TUSHARE_TOKEN' in line and '=' in line:
                        token = line.split('=', 1)[1].strip().strip('"').strip("'")
        return ts.pro_api(token)
    
    def get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日历"""
        df = self.pro.trade_cal(exchange='SSE', start_date=start_date, end_date=end_date, is_open='1')
        return df['cal_date'].tolist()
    
    def fetch_valuation_by_date(self, trade_date: str) -> int:
        """获取单日期估值因子"""
        try:
            df = self.pro.daily_basic(trade_date=trade_date)
            if df is None or df.empty:
                return 0
            
            cols = ['ts_code', 'trade_date', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 
                    'dv_ratio', 'total_mv', 'circ_mv']
            df = df[[c for c in cols if c in df.columns]].copy()
            df['update_time'] = datetime.now().isoformat()
            
            # 使用REPLACE避免重复
            cursor = self.conn.cursor()
            for _, row in df.iterrows():
                cursor.execute("""
                    REPLACE INTO stock_valuation_factors 
                    (ts_code, trade_date, pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, total_mv, circ_mv, update_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['ts_code'], row['trade_date'], row.get('pe'), row.get('pe_ttm'),
                    row.get('pb'), row.get('ps'), row.get('ps_ttm'), row.get('dv_ratio'),
                    row.get('total_mv'), row.get('circ_mv'), row['update_time']
                ))
            self.conn.commit()
            
            return len(df)
        except Exception as e:
            print(f"   ❌ {trade_date} 失败: {e}")
            return 0
    
    def fetch_valuation_history(self, start_date: str, end_date: str):
        """批量获取历史估值因子"""
        print(f"\n{'='*60}")
        print(f"📊 获取估值因子历史数据")
        print(f"   时间范围: {start_date} 至 {end_date}")
        print(f"{'='*60}\n")
        
        # 获取交易日历
        trade_dates = self.get_trade_dates(start_date, end_date)
        print(f"📅 共 {len(trade_dates)} 个交易日")
        
        total_saved = 0
        for i, date in enumerate(trade_dates, 1):
            if i % 100 == 0 or i == 1:
                print(f"   进度: {i}/{len(trade_dates)} - 已保存 {total_saved} 条")
            
            count = self.fetch_valuation_by_date(date)
            total_saved += count
            
            # 限流：每秒最多10次
            time.sleep(0.12)
        
        print(f"\n✅ 估值因子完成: 共 {total_saved} 条")
        return total_saved
    
    def fetch_daily_for_technical(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取日线数据并计算技术指标"""
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is None or len(df) < 30:
                return pd.DataFrame()
            
            df = df.sort_values('trade_date')
            
            # RSI_14
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14, min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
            rs = gain / loss
            df['rsi_14'] = 100 - (100 / (1 + rs))
            
            # MACD
            exp1 = df['close'].ewm(span=12, adjust=False).mean()
            exp2 = df['close'].ewm(span=26, adjust=False).mean()
            df['macd'] = exp1 - exp2
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_hist'] = df['macd'] - df['macd_signal']
            
            # ATR
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift())
            df['tr3'] = abs(df['low'] - df['close'].shift())
            df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            df['atr_14'] = df['tr'].rolling(window=14, min_periods=1).mean()
            
            return df[['ts_code', 'trade_date', 'close', 'rsi_14', 'macd', 'macd_signal', 'macd_hist', 'atr_14']].copy()
            
        except Exception as e:
            print(f"   ❌ {ts_code} 获取失败: {e}")
            return pd.DataFrame()
    
    def save_technical_batch(self, df: pd.DataFrame):
        """批量保存技术指标"""
        if df.empty:
            return 0
        
        df['update_time'] = datetime.now().isoformat()
        
        cursor = self.conn.cursor()
        saved = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    REPLACE INTO stock_technical_factors 
                    (ts_code, trade_date, close, rsi_14, macd, macd_signal, macd_hist, atr_14, update_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row['ts_code'], row['trade_date'], row['close'], row['rsi_14'],
                    row['macd'], row['macd_signal'], row['macd_hist'], row['atr_14'],
                    row['update_time']
                ))
                saved += 1
            except:
                pass
        
        self.conn.commit()
        return saved
    
    def fetch_technical_history(self, start_date: str, end_date: str, max_stocks: int = None):
        """批量获取历史技术指标"""
        print(f"\n{'='*60}")
        print(f"📊 获取技术指标历史数据")
        print(f"   时间范围: {start_date} 至 {end_date}")
        print(f"{'='*60}\n")
        
        # 获取股票列表
        stocks_df = pd.read_sql("SELECT DISTINCT ts_code FROM stock_basic", self.conn)
        stock_list = stocks_df['ts_code'].tolist()
        
        if max_stocks:
            stock_list = stock_list[:max_stocks]
        
        print(f"📋 共 {len(stock_list)} 只股票")
        print(f"   预估数据量: {len(stock_list)} * ~500交易日 = ~{len(stock_list)*500/10000:.0f}万条\n")
        
        total_saved = 0
        for i, ts_code in enumerate(stock_list, 1):
            if i % 50 == 0 or i == 1:
                print(f"   进度: {i}/{len(stock_list)} - 已保存 {total_saved} 条")
            
            df = self.fetch_daily_for_technical(ts_code, start_date, end_date)
            if not df.empty:
                count = self.save_technical_batch(df)
                total_saved += count
            
            # 限流
            time.sleep(0.05)
        
        print(f"\n✅ 技术指标完成: 共 {total_saved} 条")
        return total_saved
    
    def create_tables(self):
        """创建表结构"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_valuation_factors (
            ts_code TEXT,
            trade_date TEXT,
            pe REAL,
            pe_ttm REAL,
            pb REAL,
            ps REAL,
            ps_ttm REAL,
            dv_ratio REAL,
            total_mv REAL,
            circ_mv REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_technical_factors (
            ts_code TEXT,
            trade_date TEXT,
            close REAL,
            rsi_14 REAL,
            macd REAL,
            macd_signal REAL,
            macd_hist REAL,
            atr_14 REAL,
            update_time TEXT,
            PRIMARY KEY (ts_code, trade_date)
        )
        """)
        
        # 创建索引加速查询
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_valuation_date ON stock_valuation_factors(trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_valuation_code ON stock_valuation_factors(ts_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_technical_date ON stock_technical_factors(trade_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_technical_code ON stock_technical_factors(ts_code)")
        
        self.conn.commit()
        print("✅ 数据库表和索引创建完成")
    
    def check_existing_data(self) -> Tuple[int, int]:
        """检查已有数据量"""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM stock_valuation_factors")
        valuation_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM stock_technical_factors")
        technical_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM stock_valuation_factors")
        val_range = cursor.fetchone()
        
        return valuation_count, technical_count, val_range
    
    def close(self):
        """关闭连接"""
        self.conn.close()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Tushare历史因子回补 (2018-2026)')
    parser.add_argument('--mode', choices=['valuation', 'technical', 'all'], default='all',
                       help='回补类型: valuation(估值)/technical(技术)/all(全部)')
    parser.add_argument('--start', type=str, default='20180101', help='开始日期')
    parser.add_argument('--end', type=str, default='20261231', help='结束日期')
    parser.add_argument('--max-stocks', type=int, help='最多处理股票数(测试用)')
    
    args = parser.parse_args()
    
    fetcher = TushareHistoryFetcher()
    
    try:
        # 创建表
        fetcher.create_tables()
        
        # 检查已有数据
        val_count, tech_count, val_range = fetcher.check_existing_data()
        print(f"\n📊 当前数据库状态:")
        print(f"   估值因子: {val_count} 条")
        print(f"   技术指标: {tech_count} 条")
        if val_range[0]:
            print(f"   估值数据范围: {val_range[0]} - {val_range[1]}")
        
        # 执行回补
        if args.mode in ['valuation', 'all']:
            fetcher.fetch_valuation_history(args.start, args.end)
        
        if args.mode in ['technical', 'all']:
            fetcher.fetch_technical_history(args.start, args.end, args.max_stocks)
        
        print(f"\n{'='*60}")
        print("✅ 历史数据回补完成")
        print(f"{'='*60}\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
